using CodeMesh.Domain.Contracts;
using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Utilities;
using Microsoft.Build.Locator;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;
using Microsoft.CodeAnalysis.MSBuild;
using Microsoft.CodeAnalysis.Text;

namespace CodeMesh.Parser.CSharp;

public sealed class CSharpParseService
{
    private static readonly object MSBuildRegistrationLock = new();
    private static readonly HashSet<string> TestAttributeNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "Fact",
        "FactAttribute",
        "Theory",
        "TheoryAttribute",
        "Test",
        "TestAttribute",
        "TestCase",
        "TestCaseAttribute",
        "TestMethod",
        "TestMethodAttribute",
        "DataTestMethod",
        "DataTestMethodAttribute"
    };

    private static readonly SymbolDisplayFormat FullyQualifiedTypeFormat = new(
        globalNamespaceStyle: SymbolDisplayGlobalNamespaceStyle.Omitted,
        typeQualificationStyle: SymbolDisplayTypeQualificationStyle.NameAndContainingTypesAndNamespaces,
        genericsOptions: SymbolDisplayGenericsOptions.IncludeTypeParameters,
        miscellaneousOptions: SymbolDisplayMiscellaneousOptions.EscapeKeywordIdentifiers);

    public static ParserCapability Capability { get; } = new(
        "codemesh-parser-csharp",
        "csharp",
        "0.2.0",
        [".cs", ".csproj", ".sln", ".slnx"],
        ["repositoryRoot", "solutionPath", "projectPath"]);

    public async Task<ParseResult> ParseAsync(
        ParseRequest request,
        CancellationToken cancellationToken = default)
    {
        var diagnostics = new List<ParserDiagnostic>();
        var nodes = new List<CodeNode>();
        var contents = new List<CodeContent>();

        if (string.IsNullOrWhiteSpace(request.RepositoryRoot))
        {
            diagnostics.Add(new ParserDiagnostic(
                "CMSHARP000",
                "RepositoryRoot is required.",
                "error"));

            return EmptyResult(diagnostics);
        }

        var repositoryRoot = Path.GetFullPath(request.RepositoryRoot);
        if (!Directory.Exists(repositoryRoot))
        {
            diagnostics.Add(new ParserDiagnostic(
                "CMSHARP404",
                $"Repository root does not exist: {repositoryRoot}",
                "error"));

            return EmptyResult(diagnostics);
        }

        var projectContexts = await LoadProjectContextsAsync(
            request,
            repositoryRoot,
            diagnostics,
            cancellationToken).ConfigureAwait(false);
        var relationships = new List<CodeRelationship>();
        var declarationNodeIdsBySyntax = new Dictionary<SyntaxNode, string>();
        var symbolNodeIdsBySyntax = new Dictionary<SyntaxNode, string>();
        var nodeIdsBySymbolKey = new Dictionary<string, string>(StringComparer.Ordinal);
        var emittedNodeIds = new HashSet<string>(StringComparer.Ordinal);
        var emittedRelationshipIds = new HashSet<string>(StringComparer.Ordinal);

        foreach (var projectContext in projectContexts)
        {
            foreach (var context in projectContext.Files)
            {
                EmitFileNode(projectContext.ProjectName, context, nodes, contents, emittedNodeIds);
            }
        }

        foreach (var projectContext in projectContexts)
        {
            foreach (var context in projectContext.Files)
            {
                cancellationToken.ThrowIfCancellationRequested();

                var model = projectContext.Compilation.GetSemanticModel(context.SyntaxTree);
                var root = await context.SyntaxTree.GetRootAsync(cancellationToken).ConfigureAwait(false);

                ExtractDeclarationNodes(
                    projectContext.ProjectName,
                    context,
                    root,
                    model,
                    nodes,
                    contents,
                    declarationNodeIdsBySyntax,
                    symbolNodeIdsBySyntax,
                    nodeIdsBySymbolKey,
                    emittedNodeIds,
                    cancellationToken);
            }
        }

        foreach (var projectContext in projectContexts)
        {
            foreach (var context in projectContext.Files)
            {
                cancellationToken.ThrowIfCancellationRequested();

                var model = projectContext.Compilation.GetSemanticModel(context.SyntaxTree);
                var root = await context.SyntaxTree.GetRootAsync(cancellationToken).ConfigureAwait(false);

                ExtractRelationships(
                    context,
                    root,
                    model,
                    relationships,
                    declarationNodeIdsBySyntax,
                    symbolNodeIdsBySyntax,
                    nodeIdsBySymbolKey,
                    emittedRelationshipIds,
                    cancellationToken);
            }
        }

        return new ParseResult(
            Capability.WorkerName,
            Capability.Language,
            nodes,
            relationships,
            contents,
            diagnostics,
            DateTimeOffset.UtcNow);
    }

    private static ParseResult EmptyResult(IReadOnlyList<ParserDiagnostic> diagnostics)
    {
        return new ParseResult(
            Capability.WorkerName,
            Capability.Language,
            Array.Empty<CodeNode>(),
            Array.Empty<CodeRelationship>(),
            Array.Empty<CodeContent>(),
            diagnostics,
            DateTimeOffset.UtcNow);
    }

    private static async Task<IReadOnlyList<ProjectParseContext>> LoadProjectContextsAsync(
        ParseRequest request,
        string repositoryRoot,
        List<ParserDiagnostic> diagnostics,
        CancellationToken cancellationToken)
    {
        var projectPath = ResolveInputPath(request.ProjectPath, repositoryRoot);
        if (projectPath is not null && File.Exists(projectPath))
        {
            var loadedProject = await TryLoadProjectAsync(projectPath, repositoryRoot, diagnostics, cancellationToken)
                .ConfigureAwait(false);
            if (loadedProject.Count > 0)
            {
                return loadedProject;
            }
        }

        var solutionPath = ResolveInputPath(request.SolutionPath, repositoryRoot);
        if (solutionPath is not null && File.Exists(solutionPath))
        {
            var loadedSolution = await TryLoadSolutionAsync(solutionPath, repositoryRoot, diagnostics, cancellationToken)
                .ConfigureAwait(false);
            if (loadedSolution.Count > 0)
            {
                return loadedSolution;
            }
        }

        var discoveredSolution = Directory
            .EnumerateFiles(repositoryRoot, "*.sln", SearchOption.TopDirectoryOnly)
            .Concat(Directory.EnumerateFiles(repositoryRoot, "*.slnx", SearchOption.TopDirectoryOnly))
            .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
            .FirstOrDefault();
        if (discoveredSolution is not null)
        {
            var loadedSolution = await TryLoadSolutionAsync(discoveredSolution, repositoryRoot, diagnostics, cancellationToken)
                .ConfigureAwait(false);
            if (loadedSolution.Count > 0)
            {
                return loadedSolution;
            }
        }

        var discoveredProjects = Directory
            .EnumerateFiles(repositoryRoot, "*.csproj", SearchOption.AllDirectories)
            .Where(file => !IsGeneratedOutputPath(repositoryRoot, file))
            .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
            .Take(2)
            .ToArray();
        if (discoveredProjects.Length == 1)
        {
            var loadedProject = await TryLoadProjectAsync(discoveredProjects[0], repositoryRoot, diagnostics, cancellationToken)
                .ConfigureAwait(false);
            if (loadedProject.Count > 0)
            {
                return loadedProject;
            }
        }

        diagnostics.Add(new ParserDiagnostic(
            "CMSHARP010",
            "Falling back to filesystem C# parsing because no loadable project or solution was found.",
            "warning"));

        return await LoadFallbackProjectContextAsync(request, repositoryRoot, diagnostics, cancellationToken)
            .ConfigureAwait(false);
    }

    private static async Task<IReadOnlyList<ProjectParseContext>> TryLoadProjectAsync(
        string projectPath,
        string repositoryRoot,
        List<ParserDiagnostic> diagnostics,
        CancellationToken cancellationToken)
    {
        try
        {
            EnsureMSBuildRegistered();

            var workspaceDiagnostics = new List<WorkspaceDiagnostic>();
            using var workspace = CreateWorkspace(workspaceDiagnostics);
            var project = await workspace.OpenProjectAsync(projectPath, cancellationToken: cancellationToken)
                .ConfigureAwait(false);

            AddWorkspaceDiagnostics(workspaceDiagnostics, diagnostics);
            var contexts = await CreateProjectParseContextsAsync([project], repositoryRoot, diagnostics, cancellationToken)
                .ConfigureAwait(false);
            if (contexts.Count > 0)
            {
                diagnostics.Add(new ParserDiagnostic(
                    "CMSHARP011",
                    $"Loaded project with MSBuildWorkspace: {projectPath}",
                    "info"));
            }

            return contexts;
        }
        catch (Exception exception) when (exception is InvalidOperationException or NotSupportedException or IOException)
        {
            diagnostics.Add(new ParserDiagnostic(
                "CMSHARP012",
                $"Failed to load project with MSBuildWorkspace: {projectPath}. {exception.Message}",
                "warning"));
            return Array.Empty<ProjectParseContext>();
        }
    }

    private static async Task<IReadOnlyList<ProjectParseContext>> TryLoadSolutionAsync(
        string solutionPath,
        string repositoryRoot,
        List<ParserDiagnostic> diagnostics,
        CancellationToken cancellationToken)
    {
        try
        {
            EnsureMSBuildRegistered();

            var workspaceDiagnostics = new List<WorkspaceDiagnostic>();
            using var workspace = CreateWorkspace(workspaceDiagnostics);
            var solution = await workspace.OpenSolutionAsync(solutionPath, cancellationToken: cancellationToken)
                .ConfigureAwait(false);

            AddWorkspaceDiagnostics(workspaceDiagnostics, diagnostics);
            var contexts = await CreateProjectParseContextsAsync(solution.Projects, repositoryRoot, diagnostics, cancellationToken)
                .ConfigureAwait(false);
            if (contexts.Count > 0)
            {
                diagnostics.Add(new ParserDiagnostic(
                    "CMSHARP013",
                    $"Loaded solution with MSBuildWorkspace: {solutionPath}",
                    "info"));
            }

            return contexts;
        }
        catch (Exception exception) when (exception is InvalidOperationException or NotSupportedException or IOException)
        {
            diagnostics.Add(new ParserDiagnostic(
                "CMSHARP014",
                $"Failed to load solution with MSBuildWorkspace: {solutionPath}. {exception.Message}",
                "warning"));
            return Array.Empty<ProjectParseContext>();
        }
    }

    private static MSBuildWorkspace CreateWorkspace(List<WorkspaceDiagnostic> diagnostics)
    {
        var workspace = MSBuildWorkspace.Create(new Dictionary<string, string>
        {
            ["Configuration"] = "Debug"
        });
        workspace.RegisterWorkspaceFailedHandler(args => diagnostics.Add(args.Diagnostic));
        return workspace;
    }

    private static void EnsureMSBuildRegistered()
    {
        if (MSBuildLocator.IsRegistered)
        {
            return;
        }

        lock (MSBuildRegistrationLock)
        {
            if (!MSBuildLocator.IsRegistered)
            {
                MSBuildLocator.RegisterDefaults();
            }
        }
    }

    private static void AddWorkspaceDiagnostics(
        IReadOnlyList<WorkspaceDiagnostic> workspaceDiagnostics,
        List<ParserDiagnostic> diagnostics)
    {
        foreach (var diagnostic in workspaceDiagnostics)
        {
            diagnostics.Add(new ParserDiagnostic(
                "CMSHARP015",
                diagnostic.Message,
                diagnostic.Kind == WorkspaceDiagnosticKind.Failure ? "warning" : "info"));
        }
    }

    private static async Task<IReadOnlyList<ProjectParseContext>> CreateProjectParseContextsAsync(
        IEnumerable<Project> projects,
        string repositoryRoot,
        List<ParserDiagnostic> diagnostics,
        CancellationToken cancellationToken)
    {
        var contexts = new List<ProjectParseContext>();

        foreach (var project in projects.Where(project => project.Language == LanguageNames.CSharp))
        {
            cancellationToken.ThrowIfCancellationRequested();

            var compilation = await project.GetCompilationAsync(cancellationToken).ConfigureAwait(false);
            if (compilation is null)
            {
                diagnostics.Add(new ParserDiagnostic(
                    "CMSHARP016",
                    $"Project did not produce a compilation: {project.Name}",
                    "warning"));
                continue;
            }

            var files = new List<FileParseContext>();
            foreach (var document in project.Documents)
            {
                cancellationToken.ThrowIfCancellationRequested();

                var context = await TryCreateWorkspaceFileContextAsync(document, repositoryRoot, cancellationToken)
                    .ConfigureAwait(false);
                if (context is not null)
                {
                    files.Add(context);
                }
            }

            if (files.Count > 0)
            {
                contexts.Add(new ProjectParseContext(project.Name, compilation, files));
            }
        }

        return contexts;
    }

    private static async Task<FileParseContext?> TryCreateWorkspaceFileContextAsync(
        Document document,
        string repositoryRoot,
        CancellationToken cancellationToken)
    {
        if (document.SourceCodeKind != SourceCodeKind.Regular ||
            string.IsNullOrWhiteSpace(document.FilePath) ||
            !string.Equals(Path.GetExtension(document.FilePath), ".cs", StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        var fullPath = Path.GetFullPath(document.FilePath);
        if (!IsUnderDirectory(repositoryRoot, fullPath) || IsGeneratedOutputPath(repositoryRoot, fullPath))
        {
            return null;
        }

        var syntaxTree = await document.GetSyntaxTreeAsync(cancellationToken).ConfigureAwait(false);
        var sourceText = await document.GetTextAsync(cancellationToken).ConfigureAwait(false);
        if (syntaxTree is null)
        {
            return null;
        }

        return CreateFileContext(repositoryRoot, fullPath, sourceText, syntaxTree);
    }

    private static async Task<IReadOnlyList<ProjectParseContext>> LoadFallbackProjectContextAsync(
        ParseRequest request,
        string repositoryRoot,
        List<ParserDiagnostic> diagnostics,
        CancellationToken cancellationToken)
    {
        var projectName = ResolveProjectName(request, repositoryRoot);
        var fileContexts = new List<FileParseContext>();
        var files = EnumerateCSharpFiles(repositoryRoot).ToArray();

        if (files.Length == 0)
        {
            diagnostics.Add(new ParserDiagnostic(
                "CMSHARP002",
                "No C# source files were found under the repository root.",
                "warning"));
        }

        foreach (var file in files)
        {
            cancellationToken.ThrowIfCancellationRequested();

            try
            {
                var text = await File.ReadAllTextAsync(file, cancellationToken).ConfigureAwait(false);
                var relativePath = Path.GetRelativePath(repositoryRoot, file).Replace('\\', '/');
                var sourceText = SourceText.From(text);
                var syntaxTree = CSharpSyntaxTree.ParseText(
                    sourceText,
                    new CSharpParseOptions(LanguageVersion.Preview),
                    path: relativePath,
                    cancellationToken: cancellationToken);

                fileContexts.Add(CreateFileContext(repositoryRoot, file, sourceText, syntaxTree));
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                diagnostics.Add(new ParserDiagnostic(
                    "CMSHARP003",
                    $"Failed to read {file}: {exception.Message}",
                    "warning",
                    SourceSpan.Unknown(Path.GetRelativePath(repositoryRoot, file).Replace('\\', '/'))));
            }
        }

        if (fileContexts.Count == 0)
        {
            return Array.Empty<ProjectParseContext>();
        }

        var compilation = CSharpCompilation.Create(
            projectName,
            fileContexts.Select(context => context.SyntaxTree),
            CreateMetadataReferences(),
            new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary));

        return [new ProjectParseContext(projectName, compilation, fileContexts)];
    }

    private static FileParseContext CreateFileContext(
        string repositoryRoot,
        string fullPath,
        SourceText sourceText,
        SyntaxTree syntaxTree)
    {
        var text = sourceText.ToString();
        var relativePath = Path.GetRelativePath(repositoryRoot, fullPath).Replace('\\', '/');
        var contentHash = CodeMeshHash.Sha256Hex(text);
        var isTestFile = IsTestFilePath(relativePath);

        return new FileParseContext(
            fullPath,
            relativePath,
            text,
            contentHash,
            FileNodeId(relativePath),
            syntaxTree,
            isTestFile);
    }

    private static void EmitFileNode(
        string projectName,
        FileParseContext context,
        List<CodeNode> nodes,
        List<CodeContent> contents,
        HashSet<string> emittedNodeIds)
    {
        if (!emittedNodeIds.Add(context.FileNodeId))
        {
            return;
        }

        var now = DateTimeOffset.UtcNow;
        nodes.Add(new CodeNode(
            context.FileNodeId,
            context.FileNodeId,
            context.IsTestFile ? CodeNodeKind.TestFile : CodeNodeKind.File,
            Path.GetFileName(context.FullPath),
            "csharp",
            projectName,
            new SourceSpan(context.RelativePath, 1, 1, CountLines(context.Text), 1),
            context.ContentHash,
            new Dictionary<string, string>
            {
                ["parser"] = "codemesh-parser-csharp",
                ["extraction"] = "file",
                ["isTestFile"] = context.IsTestFile.ToString().ToLowerInvariant()
            }));

        contents.Add(new CodeContent(
            context.ContentHash,
            context.Text,
            "text/x-csharp",
            now,
            now));
    }

    private static IEnumerable<string> EnumerateCSharpFiles(string repositoryRoot)
    {
        return Directory.EnumerateFiles(repositoryRoot, "*.cs", SearchOption.AllDirectories)
            .Where(file => !IsGeneratedOutputPath(repositoryRoot, file));
    }

    private static string FileNodeId(string relativePath)
    {
        return $"csharp:file:{relativePath}";
    }

    private static string DeclarationNodeId(string symbolNodeId, string relativePath, SourceSpan span)
    {
        return $"csharp:decl:{symbolNodeId}:{relativePath}:{span.StartLine}:{span.StartColumn}";
    }

    private static void ExtractDeclarationNodes(
        string projectName,
        FileParseContext context,
        SyntaxNode root,
        SemanticModel model,
        List<CodeNode> nodes,
        List<CodeContent> contents,
        Dictionary<SyntaxNode, string> declarationNodeIdsBySyntax,
        Dictionary<SyntaxNode, string> symbolNodeIdsBySyntax,
        Dictionary<string, string> nodeIdsBySymbolKey,
        HashSet<string> emittedNodeIds,
        CancellationToken cancellationToken)
    {
        foreach (var declaration in EnumerateSymbolDeclarations(root))
        {
            cancellationToken.ThrowIfCancellationRequested();

            var symbol = GetDeclaredSymbol(model, declaration, cancellationToken);
            if (symbol is null)
            {
                continue;
            }

            var kind = ToNodeKind(symbol, declaration, context);
            var span = ToSourceSpan(declaration, context.RelativePath);
            var source = declaration.ToFullString();
            var contentHash = CodeMeshHash.Sha256Hex(source);
            var stableKey = SymbolStableKey(symbol, declaration);
            var symbolNodeId = stableKey;
            var declarationNodeId = DeclarationNodeId(stableKey, context.RelativePath, span);
            var now = DateTimeOffset.UtcNow;

            if (emittedNodeIds.Add(symbolNodeId))
            {
                var symbolContent = SymbolContent(symbol);
                var symbolContentHash = CodeMeshHash.Sha256Hex(symbolContent);
                nodes.Add(new CodeNode(
                    symbolNodeId,
                    stableKey,
                    kind,
                    SymbolDisplayName(symbol, declaration),
                    "csharp",
                    projectName,
                    SourceSpan.Unknown(context.RelativePath),
                    symbolContentHash,
                    BuildSymbolMetadata(symbol, declaration, context)));

                contents.Add(new CodeContent(
                    symbolContentHash,
                    symbolContent,
                    "text/x-csharp-symbol",
                    now,
                    now));
            }

            if (emittedNodeIds.Add(declarationNodeId))
            {
                nodes.Add(new CodeNode(
                    declarationNodeId,
                    declarationNodeId,
                    CodeNodeKind.Declaration,
                    SymbolDisplayName(symbol, declaration),
                    "csharp",
                    projectName,
                    span,
                    contentHash,
                    BuildDeclarationMetadata(symbol, declaration, stableKey)));

                contents.Add(new CodeContent(
                    contentHash,
                    source,
                    "text/x-csharp-fragment",
                    now,
                    now));
            }

            declarationNodeIdsBySyntax[declaration] = declarationNodeId;
            symbolNodeIdsBySyntax[declaration] = symbolNodeId;

            foreach (var symbolKey in SymbolLookupKeys(symbol))
            {
                nodeIdsBySymbolKey.TryAdd(symbolKey, symbolNodeId);
            }
        }
    }

    private static void ExtractRelationships(
        FileParseContext context,
        SyntaxNode root,
        SemanticModel model,
        List<CodeRelationship> relationships,
        Dictionary<SyntaxNode, string> declarationNodeIdsBySyntax,
        Dictionary<SyntaxNode, string> symbolNodeIdsBySyntax,
        Dictionary<string, string> nodeIdsBySymbolKey,
        HashSet<string> emittedRelationshipIds,
        CancellationToken cancellationToken)
    {
        foreach (var declaration in EnumerateSymbolDeclarations(root))
        {
            cancellationToken.ThrowIfCancellationRequested();

            if (!declarationNodeIdsBySyntax.TryGetValue(declaration, out var declarationNodeId) ||
                !symbolNodeIdsBySyntax.TryGetValue(declaration, out var symbolNodeId))
            {
                continue;
            }

            var parentDeclarationNodeId = FindParentDeclarationNodeId(
                context.FileNodeId,
                declaration,
                declarationNodeIdsBySyntax);
            AddRelationship(
                relationships,
                emittedRelationshipIds,
                parentDeclarationNodeId,
                declarationNodeId,
                CodeRelationshipKind.Contains,
                "contains");

            AddRelationship(
                relationships,
                emittedRelationshipIds,
                declarationNodeId,
                symbolNodeId,
                CodeRelationshipKind.Defines,
                "defines");

            var parentSymbolNodeId = FindParentSymbolNodeId(declaration, symbolNodeIdsBySyntax);
            if (!string.IsNullOrWhiteSpace(parentSymbolNodeId) &&
                !string.Equals(parentSymbolNodeId, symbolNodeId, StringComparison.Ordinal))
            {
                AddRelationship(
                    relationships,
                    emittedRelationshipIds,
                    parentSymbolNodeId,
                    symbolNodeId,
                    CodeRelationshipKind.Contains,
                    "contains");
            }

            var symbol = GetDeclaredSymbol(model, declaration, cancellationToken);
            if (symbol is INamedTypeSymbol typeSymbol)
            {
                AddTypeRelationships(typeSymbol, symbolNodeId, relationships, nodeIdsBySymbolKey, emittedRelationshipIds);
            }

            if (symbol is IMethodSymbol methodSymbol)
            {
                AddReturnsRelationship(methodSymbol.ReturnType, symbolNodeId, relationships, nodeIdsBySymbolKey, emittedRelationshipIds);
                AddOverridesRelationship(methodSymbol.OverriddenMethod, symbolNodeId, relationships, nodeIdsBySymbolKey, emittedRelationshipIds);
            }

            if (symbol is IPropertySymbol propertySymbol)
            {
                AddReturnsRelationship(propertySymbol.Type, symbolNodeId, relationships, nodeIdsBySymbolKey, emittedRelationshipIds);
                AddOverridesRelationship(propertySymbol.OverriddenProperty, symbolNodeId, relationships, nodeIdsBySymbolKey, emittedRelationshipIds);
            }

            if (symbol is IFieldSymbol fieldSymbol)
            {
                AddReturnsRelationship(fieldSymbol.Type, symbolNodeId, relationships, nodeIdsBySymbolKey, emittedRelationshipIds);
            }

            if (symbol is IEventSymbol eventSymbol)
            {
                AddReturnsRelationship(eventSymbol.Type, symbolNodeId, relationships, nodeIdsBySymbolKey, emittedRelationshipIds);
                AddOverridesRelationship(eventSymbol.OverriddenEvent, symbolNodeId, relationships, nodeIdsBySymbolKey, emittedRelationshipIds);
            }

            if (symbol is IParameterSymbol parameterSymbol)
            {
                AddParameterRelationship(parameterSymbol, symbolNodeId, relationships, nodeIdsBySymbolKey, emittedRelationshipIds);
            }

            AddBodyReferenceRelationships(
                declaration,
                symbolNodeId,
                model,
                relationships,
                nodeIdsBySymbolKey,
                emittedRelationshipIds,
                cancellationToken);
        }
    }

    private static void AddBodyReferenceRelationships(
        SyntaxNode declaration,
        string sourceNodeId,
        SemanticModel model,
        List<CodeRelationship> relationships,
        Dictionary<string, string> nodeIdsBySymbolKey,
        HashSet<string> emittedRelationshipIds,
        CancellationToken cancellationToken)
    {
        if (declaration is ParameterSyntax ||
            declaration is BaseNamespaceDeclarationSyntax ||
            declaration is BaseTypeDeclarationSyntax ||
            declaration is DelegateDeclarationSyntax)
        {
            return;
        }

        foreach (var invocation in declaration.DescendantNodes().OfType<InvocationExpressionSyntax>())
        {
            cancellationToken.ThrowIfCancellationRequested();

            var methodSymbol = ResolveMethodSymbol(
                model.GetSymbolInfo(invocation, cancellationToken));
            if (methodSymbol is not null)
            {
                AddSymbolRelationship(
                    sourceNodeId,
                    methodSymbol.OriginalDefinition,
                    CodeRelationshipKind.Invokes,
                    "invokes",
                    relationships,
                    nodeIdsBySymbolKey,
                    emittedRelationshipIds);
            }
        }

        foreach (var objectCreation in declaration.DescendantNodes().OfType<ObjectCreationExpressionSyntax>())
        {
            cancellationToken.ThrowIfCancellationRequested();

            var constructorSymbol = ResolveMethodSymbol(
                model.GetSymbolInfo(objectCreation, cancellationToken));
            if (constructorSymbol is not null)
            {
                AddSymbolRelationship(
                    sourceNodeId,
                    constructorSymbol.OriginalDefinition,
                    CodeRelationshipKind.Invokes,
                    "constructs",
                    relationships,
                    nodeIdsBySymbolKey,
                    emittedRelationshipIds);
            }
        }

        foreach (var objectCreation in declaration.DescendantNodes().OfType<ImplicitObjectCreationExpressionSyntax>())
        {
            cancellationToken.ThrowIfCancellationRequested();

            var constructorSymbol = ResolveMethodSymbol(
                model.GetSymbolInfo(objectCreation, cancellationToken));
            if (constructorSymbol is not null)
            {
                AddSymbolRelationship(
                    sourceNodeId,
                    constructorSymbol.OriginalDefinition,
                    CodeRelationshipKind.Invokes,
                    "constructs",
                    relationships,
                    nodeIdsBySymbolKey,
                    emittedRelationshipIds);
            }
        }

        foreach (var assignment in declaration.DescendantNodes().OfType<AssignmentExpressionSyntax>())
        {
            cancellationToken.ThrowIfCancellationRequested();

            AddAccessRelationship(
                sourceNodeId,
                assignment.Left,
                model,
                CodeRelationshipKind.Writes,
                "writes",
                relationships,
                nodeIdsBySymbolKey,
                emittedRelationshipIds,
                cancellationToken);
        }

        foreach (var expression in declaration.DescendantNodes().OfType<ExpressionSyntax>())
        {
            cancellationToken.ThrowIfCancellationRequested();

            if (!IsReadableReferenceExpression(expression))
            {
                continue;
            }

            AddAccessRelationship(
                sourceNodeId,
                expression,
                model,
                CodeRelationshipKind.Reads,
                "reads",
                relationships,
                nodeIdsBySymbolKey,
                emittedRelationshipIds,
                cancellationToken);
        }
    }

    private static bool IsReadableReferenceExpression(ExpressionSyntax expression)
    {
        if (expression.Parent is AssignmentExpressionSyntax assignment &&
            assignment.Left == expression)
        {
            return false;
        }

        return expression is IdentifierNameSyntax or MemberAccessExpressionSyntax;
    }

    private static IMethodSymbol? ResolveMethodSymbol(SymbolInfo symbolInfo)
    {
        if (symbolInfo.Symbol is IMethodSymbol methodSymbol)
        {
            return methodSymbol;
        }

        var candidates = symbolInfo.CandidateSymbols
            .OfType<IMethodSymbol>()
            .Select(candidate => (ISymbol)candidate.OriginalDefinition)
            .Distinct(SymbolEqualityComparer.Default)
            .OfType<IMethodSymbol>()
            .ToArray();
        return candidates.Length == 1 ? candidates[0] : null;
    }

    private static void AddAccessRelationship(
        string sourceNodeId,
        ExpressionSyntax expression,
        SemanticModel model,
        CodeRelationshipKind kind,
        string label,
        List<CodeRelationship> relationships,
        Dictionary<string, string> nodeIdsBySymbolKey,
        HashSet<string> emittedRelationshipIds,
        CancellationToken cancellationToken)
    {
        var symbol = model.GetSymbolInfo(expression, cancellationToken).Symbol;
        if (symbol is not (IPropertySymbol or IFieldSymbol or IEventSymbol))
        {
            return;
        }

        AddSymbolRelationship(
            sourceNodeId,
            symbol,
            kind,
            label,
            relationships,
            nodeIdsBySymbolKey,
            emittedRelationshipIds);
    }

    private static IEnumerable<SyntaxNode> EnumerateSymbolDeclarations(SyntaxNode root)
    {
        return root.DescendantNodes(static node =>
                node is not AccessorListSyntax &&
                node is not AttributeListSyntax)
            .Where(static node =>
                node is BaseNamespaceDeclarationSyntax ||
                node is TypeDeclarationSyntax ||
                node is EnumDeclarationSyntax ||
                node is DelegateDeclarationSyntax ||
                node is MethodDeclarationSyntax ||
                node is ConstructorDeclarationSyntax ||
                node is PropertyDeclarationSyntax ||
                node is FieldDeclarationSyntax ||
                node is EventFieldDeclarationSyntax ||
                node is EventDeclarationSyntax ||
                node is ParameterSyntax);
    }

    private static ISymbol? GetDeclaredSymbol(
        SemanticModel model,
        SyntaxNode declaration,
        CancellationToken cancellationToken)
    {
        return declaration switch
        {
            BaseNamespaceDeclarationSyntax namespaceDeclaration => model.GetDeclaredSymbol(namespaceDeclaration, cancellationToken),
            BaseTypeDeclarationSyntax typeDeclaration => model.GetDeclaredSymbol(typeDeclaration, cancellationToken),
            DelegateDeclarationSyntax delegateDeclaration => model.GetDeclaredSymbol(delegateDeclaration, cancellationToken),
            MethodDeclarationSyntax methodDeclaration => model.GetDeclaredSymbol(methodDeclaration, cancellationToken),
            ConstructorDeclarationSyntax constructorDeclaration => model.GetDeclaredSymbol(constructorDeclaration, cancellationToken),
            PropertyDeclarationSyntax propertyDeclaration => model.GetDeclaredSymbol(propertyDeclaration, cancellationToken),
            EventDeclarationSyntax eventDeclaration => model.GetDeclaredSymbol(eventDeclaration, cancellationToken),
            ParameterSyntax parameter => model.GetDeclaredSymbol(parameter, cancellationToken),
            FieldDeclarationSyntax fieldDeclaration => fieldDeclaration.Declaration.Variables.Count == 1
                ? model.GetDeclaredSymbol(fieldDeclaration.Declaration.Variables[0], cancellationToken)
                : null,
            EventFieldDeclarationSyntax eventFieldDeclaration => eventFieldDeclaration.Declaration.Variables.Count == 1
                ? model.GetDeclaredSymbol(eventFieldDeclaration.Declaration.Variables[0], cancellationToken)
                : null,
            _ => null
        };
    }

    private static string FindParentDeclarationNodeId(
        string fileNodeId,
        SyntaxNode declaration,
        Dictionary<SyntaxNode, string> declarationNodeIdsBySyntax)
    {
        for (var parent = declaration.Parent; parent is not null; parent = parent.Parent)
        {
            if (declarationNodeIdsBySyntax.TryGetValue(parent, out var parentNodeId))
            {
                return parentNodeId;
            }
        }

        return fileNodeId;
    }

    private static string? FindParentSymbolNodeId(
        SyntaxNode declaration,
        Dictionary<SyntaxNode, string> symbolNodeIdsBySyntax)
    {
        for (var parent = declaration.Parent; parent is not null; parent = parent.Parent)
        {
            if (symbolNodeIdsBySyntax.TryGetValue(parent, out var parentNodeId))
            {
                return parentNodeId;
            }
        }

        return null;
    }

    private static void AddTypeRelationships(
        INamedTypeSymbol symbol,
        string sourceNodeId,
        List<CodeRelationship> relationships,
        Dictionary<string, string> nodeIdsBySymbolKey,
        HashSet<string> emittedRelationshipIds)
    {
        if (symbol.BaseType is not null && symbol.BaseType.SpecialType != SpecialType.System_Object)
        {
            AddSymbolRelationship(
                sourceNodeId,
                symbol.BaseType,
                CodeRelationshipKind.Inherits,
                "inherits",
                relationships,
                nodeIdsBySymbolKey,
                emittedRelationshipIds);
        }

        foreach (var interfaceSymbol in symbol.Interfaces)
        {
            AddSymbolRelationship(
                sourceNodeId,
                interfaceSymbol,
                CodeRelationshipKind.Implements,
                "implements",
                relationships,
                nodeIdsBySymbolKey,
                emittedRelationshipIds);
        }
    }

    private static void AddReturnsRelationship(
        ITypeSymbol? typeSymbol,
        string sourceNodeId,
        List<CodeRelationship> relationships,
        Dictionary<string, string> nodeIdsBySymbolKey,
        HashSet<string> emittedRelationshipIds)
    {
        if (typeSymbol is null || typeSymbol.SpecialType == SpecialType.System_Void)
        {
            return;
        }

        AddSymbolRelationship(
            sourceNodeId,
            typeSymbol,
            CodeRelationshipKind.Returns,
            "returns",
            relationships,
            nodeIdsBySymbolKey,
            emittedRelationshipIds);
    }

    private static void AddOverridesRelationship(
        ISymbol? overriddenSymbol,
        string sourceNodeId,
        List<CodeRelationship> relationships,
        Dictionary<string, string> nodeIdsBySymbolKey,
        HashSet<string> emittedRelationshipIds)
    {
        if (overriddenSymbol is null)
        {
            return;
        }

        AddSymbolRelationship(
            sourceNodeId,
            overriddenSymbol,
            CodeRelationshipKind.Overrides,
            "overrides",
            relationships,
            nodeIdsBySymbolKey,
            emittedRelationshipIds);
    }

    private static void AddParameterRelationship(
        IParameterSymbol parameterSymbol,
        string parameterNodeId,
        List<CodeRelationship> relationships,
        Dictionary<string, string> nodeIdsBySymbolKey,
        HashSet<string> emittedRelationshipIds)
    {
        AddSymbolRelationship(
            parameterNodeId,
            parameterSymbol.Type,
            CodeRelationshipKind.UsesType,
            "uses-type",
            relationships,
            nodeIdsBySymbolKey,
            emittedRelationshipIds);
    }

    private static void AddSymbolRelationship(
        string sourceNodeId,
        ISymbol targetSymbol,
        CodeRelationshipKind kind,
        string label,
        List<CodeRelationship> relationships,
        Dictionary<string, string> nodeIdsBySymbolKey,
        HashSet<string> emittedRelationshipIds)
    {
        var targetNodeId = SymbolLookupKeys(targetSymbol)
            .Select(key => nodeIdsBySymbolKey.GetValueOrDefault(key))
            .FirstOrDefault(nodeId => !string.IsNullOrWhiteSpace(nodeId));
        if (string.IsNullOrWhiteSpace(targetNodeId))
        {
            return;
        }

        AddRelationship(relationships, emittedRelationshipIds, sourceNodeId, targetNodeId, kind, label);
    }

    private static void AddRelationship(
        List<CodeRelationship> relationships,
        HashSet<string> emittedRelationshipIds,
        string sourceNodeId,
        string targetNodeId,
        CodeRelationshipKind kind,
        string label)
    {
        var relationship = Relationship(sourceNodeId, targetNodeId, kind, label);
        if (emittedRelationshipIds.Add(relationship.Id))
        {
            relationships.Add(relationship);
        }
    }

    private static CodeRelationship Relationship(
        string sourceNodeId,
        string targetNodeId,
        CodeRelationshipKind kind,
        string label)
    {
        return new CodeRelationship(
            CodeMeshHash.StableId(sourceNodeId, targetNodeId, kind.ToString(), label),
            sourceNodeId,
            targetNodeId,
            kind,
            label,
            new Dictionary<string, string>
            {
                ["parser"] = "codemesh-parser-csharp",
                ["extraction"] = "roslyn"
            });
    }

    private static CodeNodeKind ToNodeKind(ISymbol symbol, SyntaxNode declaration)
    {
        return symbol switch
        {
            INamespaceSymbol => CodeNodeKind.Namespace,
            INamedTypeSymbol { TypeKind: TypeKind.Class } => CodeNodeKind.Class,
            INamedTypeSymbol { TypeKind: TypeKind.Interface } => CodeNodeKind.Interface,
            INamedTypeSymbol { TypeKind: TypeKind.Struct } => CodeNodeKind.Struct,
            INamedTypeSymbol { TypeKind: TypeKind.Enum } => CodeNodeKind.Enum,
            INamedTypeSymbol { TypeKind: TypeKind.Delegate } => CodeNodeKind.Delegate,
            IMethodSymbol { MethodKind: MethodKind.Constructor } => CodeNodeKind.Constructor,
            IMethodSymbol methodSymbol when IsTestCase(methodSymbol, declaration) => CodeNodeKind.TestCase,
            IMethodSymbol => CodeNodeKind.Method,
            IPropertySymbol => CodeNodeKind.Property,
            IFieldSymbol => declaration is EventFieldDeclarationSyntax ? CodeNodeKind.Event : CodeNodeKind.Field,
            IEventSymbol => CodeNodeKind.Event,
            IParameterSymbol => CodeNodeKind.Parameter,
            _ => CodeNodeKind.Unknown
        };
    }

    private static SourceSpan ToSourceSpan(SyntaxNode declaration, string relativePath)
    {
        var lineSpan = declaration.SyntaxTree.GetLineSpan(declaration.Span);
        return new SourceSpan(
            relativePath,
            lineSpan.StartLinePosition.Line + 1,
            lineSpan.StartLinePosition.Character + 1,
            lineSpan.EndLinePosition.Line + 1,
            lineSpan.EndLinePosition.Character + 1);
    }

    private static CodeNodeKind ToNodeKind(ISymbol symbol, SyntaxNode declaration, FileParseContext context)
    {
        if (symbol is IMethodSymbol methodSymbol && IsTestCase(methodSymbol, declaration, context))
        {
            return CodeNodeKind.TestCase;
        }

        return ToNodeKind(symbol, declaration);
    }

    private static IReadOnlyDictionary<string, string> BuildSymbolMetadata(
        ISymbol symbol,
        SyntaxNode declaration,
        FileParseContext context)
    {
        var metadata = new Dictionary<string, string>
        {
            ["parser"] = "codemesh-parser-csharp",
            ["extraction"] = "roslyn",
            ["nodeRole"] = "symbol",
            ["symbolKind"] = symbol.Kind.ToString(),
            ["display"] = symbol.ToDisplayString(SymbolDisplayFormat.CSharpErrorMessageFormat),
            ["isTestFile"] = context.IsTestFile.ToString().ToLowerInvariant()
        };

        if (symbol.ContainingNamespace is { IsGlobalNamespace: false } containingNamespace)
        {
            metadata["namespace"] = containingNamespace.ToDisplayString();
        }

        if (symbol.ContainingType is not null)
        {
            metadata["containingType"] = symbol.ContainingType.ToDisplayString(SymbolDisplayFormat.CSharpErrorMessageFormat);
        }

        if (declaration is MemberDeclarationSyntax memberDeclaration)
        {
            metadata["modifiers"] = string.Join(" ", memberDeclaration.Modifiers.Select(modifier => modifier.Text));
        }

        if (symbol is IMethodSymbol methodSymbol && IsTestCase(methodSymbol, declaration, context))
        {
            metadata["testRole"] = "case";
            metadata["testFramework"] = TestFramework(declaration) ?? "convention";
        }

        return metadata;
    }

    private static bool IsTestCase(IMethodSymbol methodSymbol, SyntaxNode declaration)
    {
        return IsTestCase(methodSymbol, declaration, null);
    }

    private static bool IsTestCase(IMethodSymbol methodSymbol, SyntaxNode declaration, FileParseContext? context)
    {
        if (methodSymbol.MethodKind != MethodKind.Ordinary)
        {
            return false;
        }

        if (HasTestAttribute(declaration))
        {
            return true;
        }

        return context?.IsTestFile == true &&
            methodSymbol.Name.StartsWith("Test", StringComparison.Ordinal);
    }

    private static string? TestFramework(SyntaxNode declaration)
    {
        foreach (var name in AttributeNames(declaration))
        {
            if (name is "Fact" or "FactAttribute" or "Theory" or "TheoryAttribute")
            {
                return "xunit";
            }

            if (name is "Test" or "TestAttribute" or "TestCase" or "TestCaseAttribute")
            {
                return "nunit";
            }

            if (name is "TestMethod" or "TestMethodAttribute" or "DataTestMethod" or "DataTestMethodAttribute")
            {
                return "mstest";
            }
        }

        return null;
    }

    private static bool HasTestAttribute(SyntaxNode declaration)
    {
        return AttributeNames(declaration).Any(name => TestAttributeNames.Contains(name));
    }

    private static IEnumerable<string> AttributeNames(SyntaxNode declaration)
    {
        return declaration switch
        {
            MemberDeclarationSyntax memberDeclaration => memberDeclaration.AttributeLists
                .SelectMany(list => list.Attributes)
                .Select(attribute => attribute.Name.ToString().Split('.').Last()),
            LocalFunctionStatementSyntax localFunction => localFunction.AttributeLists
                .SelectMany(list => list.Attributes)
                .Select(attribute => attribute.Name.ToString().Split('.').Last()),
            _ => []
        };
    }

    private static IReadOnlyDictionary<string, string> BuildDeclarationMetadata(
        ISymbol symbol,
        SyntaxNode declaration,
        string symbolNodeId)
    {
        var metadata = new Dictionary<string, string>
        {
            ["parser"] = "codemesh-parser-csharp",
            ["extraction"] = "roslyn",
            ["nodeRole"] = "declaration",
            ["symbolId"] = symbolNodeId,
            ["symbolKind"] = symbol.Kind.ToString(),
            ["syntaxKind"] = declaration.Kind().ToString(),
            ["display"] = symbol.ToDisplayString(SymbolDisplayFormat.CSharpErrorMessageFormat)
        };

        if (symbol.ContainingNamespace is { IsGlobalNamespace: false } containingNamespace)
        {
            metadata["namespace"] = containingNamespace.ToDisplayString();
        }

        if (symbol.ContainingType is not null)
        {
            metadata["containingType"] = symbol.ContainingType.ToDisplayString(SymbolDisplayFormat.CSharpErrorMessageFormat);
        }

        if (declaration is MemberDeclarationSyntax memberDeclaration)
        {
            metadata["modifiers"] = string.Join(" ", memberDeclaration.Modifiers.Select(modifier => modifier.Text));
        }

        return metadata;
    }

    private static string SymbolContent(ISymbol symbol)
    {
        return symbol.ToDisplayString(SymbolDisplayFormat.CSharpErrorMessageFormat);
    }

    private static string SymbolStableKey(ISymbol symbol, SyntaxNode declaration)
    {
        var symbolKey = SymbolLookupKey(symbol);
        if (!string.IsNullOrWhiteSpace(symbolKey))
        {
            return symbolKey;
        }

        return $"csharp:syntax:{declaration.SyntaxTree.FilePath}:{declaration.SpanStart}:{symbol.Name}";
    }

    private static string SymbolLookupKey(ISymbol symbol)
    {
        return symbol switch
        {
            INamespaceSymbol namespaceSymbol => namespaceSymbol.IsGlobalNamespace
                ? string.Empty
                : $"csharp:namespace:{namespaceSymbol.ToDisplayString(FullyQualifiedTypeFormat)}",
            INamedTypeSymbol typeSymbol => $"csharp:type:{TypeDefinitionName(typeSymbol)}",
            IMethodSymbol methodSymbol => methodSymbol.MethodKind == MethodKind.Constructor ||
                                          methodSymbol.MethodKind == MethodKind.StaticConstructor
                ? $"csharp:ctor:{MethodSignature(methodSymbol)}"
                : $"csharp:method:{MethodSignature(methodSymbol)}",
            IPropertySymbol propertySymbol => $"csharp:property:{PropertySignature(propertySymbol)}",
            IFieldSymbol fieldSymbol => $"csharp:field:{MemberOwnerName(fieldSymbol)}.{fieldSymbol.Name}",
            IEventSymbol eventSymbol => $"csharp:event:{MemberOwnerName(eventSymbol)}.{eventSymbol.Name}",
            IParameterSymbol parameterSymbol => $"csharp:param:{ParameterOwnerSignature(parameterSymbol)}:{parameterSymbol.Ordinal}:{parameterSymbol.Name}",
            _ => string.Empty
        };
    }

    private static IEnumerable<string> SymbolLookupKeys(ISymbol symbol)
    {
        var primary = SymbolLookupKey(symbol);
        if (!string.IsNullOrWhiteSpace(primary))
        {
            yield return primary;
        }

        var documentationId = symbol.OriginalDefinition.GetDocumentationCommentId();
        if (!string.IsNullOrWhiteSpace(documentationId))
        {
            yield return $"csharp:doc:{documentationId}";
        }
    }

    private static string TypeDefinitionName(INamedTypeSymbol symbol)
    {
        return symbol.OriginalDefinition.ToDisplayString(FullyQualifiedTypeFormat);
    }

    private static string TypeReferenceName(ITypeSymbol symbol)
    {
        return symbol.ToDisplayString(FullyQualifiedTypeFormat);
    }

    private static string MemberOwnerName(ISymbol symbol)
    {
        return symbol.ContainingType is null
            ? symbol.ContainingNamespace.ToDisplayString(FullyQualifiedTypeFormat)
            : TypeDefinitionName(symbol.ContainingType);
    }

    private static string MethodSignature(IMethodSymbol symbol)
    {
        var method = symbol.OriginalDefinition;
        var owner = TypeDefinitionName(method.ContainingType);
        var parameters = ParameterTypeList(method.Parameters);

        if (method.MethodKind is MethodKind.Constructor or MethodKind.StaticConstructor)
        {
            return $"{owner}({parameters})";
        }

        return $"{owner}.{method.Name}{TypeParameterList(method.TypeParameters)}({parameters})";
    }

    private static string PropertySignature(IPropertySymbol symbol)
    {
        var property = symbol.OriginalDefinition;
        var owner = MemberOwnerName(property);
        var name = property.IsIndexer ? "this" : property.Name;

        if (property.Parameters.Length == 0)
        {
            return $"{owner}.{name}";
        }

        return $"{owner}.{name}({ParameterTypeList(property.Parameters)})";
    }

    private static string ParameterOwnerSignature(IParameterSymbol symbol)
    {
        return symbol.ContainingSymbol switch
        {
            IMethodSymbol methodSymbol => MethodSignature(methodSymbol),
            IPropertySymbol propertySymbol => PropertySignature(propertySymbol),
            ISymbol containingSymbol => SymbolLookupKey(containingSymbol),
            _ => string.Empty
        };
    }

    private static string TypeParameterList(IEnumerable<ITypeParameterSymbol> typeParameters)
    {
        var names = typeParameters.Select(parameter => parameter.Name).ToArray();
        return names.Length == 0 ? string.Empty : $"<{string.Join(",", names)}>";
    }

    private static string ParameterTypeList(IEnumerable<IParameterSymbol> parameters)
    {
        return string.Join(",", parameters.Select(ParameterTypeName));
    }

    private static string ParameterTypeName(IParameterSymbol parameter)
    {
        var typeName = TypeReferenceName(parameter.Type);
        return parameter.RefKind switch
        {
            RefKind.Ref => $"ref {typeName}",
            RefKind.Out => $"out {typeName}",
            RefKind.In => $"in {typeName}",
            _ when parameter.IsParams => $"params {typeName}",
            _ => typeName
        };
    }

    private static string SymbolDisplayName(ISymbol symbol, SyntaxNode declaration)
    {
        return symbol switch
        {
            INamespaceSymbol namespaceSymbol => namespaceSymbol.ToDisplayString(),
            IMethodSymbol { MethodKind: MethodKind.Constructor } => symbol.ContainingType?.Name ?? symbol.Name,
            _ when !string.IsNullOrWhiteSpace(symbol.Name) => symbol.Name,
            _ => declaration.Kind().ToString()
        };
    }

    private static IEnumerable<MetadataReference> CreateMetadataReferences()
    {
        var trustedPlatformAssemblies = AppContext.GetData("TRUSTED_PLATFORM_ASSEMBLIES") as string;
        if (string.IsNullOrWhiteSpace(trustedPlatformAssemblies))
        {
            yield return MetadataReference.CreateFromFile(typeof(object).Assembly.Location);
            yield break;
        }

        foreach (var assemblyPath in trustedPlatformAssemblies.Split(Path.PathSeparator))
        {
            yield return MetadataReference.CreateFromFile(assemblyPath);
        }
    }

    private static bool IsGeneratedOutputPath(string repositoryRoot, string file)
    {
        return RepositoryPathPolicy.IsIgnoredPath(repositoryRoot, file);
    }

    private static bool IsUnderDirectory(string rootPath, string candidatePath)
    {
        var root = Path.GetFullPath(rootPath).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        var candidate = Path.GetFullPath(candidatePath);
        return candidate.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase) ||
               string.Equals(candidate, root, StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsTestFilePath(string relativePath)
    {
        var fileName = Path.GetFileName(relativePath);
        if (fileName.EndsWith("Tests.cs", StringComparison.OrdinalIgnoreCase) ||
            fileName.EndsWith("Test.cs", StringComparison.OrdinalIgnoreCase) ||
            fileName.EndsWith("Spec.cs", StringComparison.OrdinalIgnoreCase) ||
            fileName.EndsWith("Specs.cs", StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        var segments = relativePath.Split('/', StringSplitOptions.RemoveEmptyEntries);
        return segments.Any(segment =>
            string.Equals(segment, "test", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(segment, "tests", StringComparison.OrdinalIgnoreCase));
    }

    private static string ResolveProjectName(ParseRequest request, string repositoryRoot)
    {
        if (!string.IsNullOrWhiteSpace(request.ProjectPath))
        {
            return Path.GetFileNameWithoutExtension(request.ProjectPath);
        }

        if (!string.IsNullOrWhiteSpace(request.SolutionPath))
        {
            return Path.GetFileNameWithoutExtension(request.SolutionPath);
        }

        return new DirectoryInfo(repositoryRoot).Name;
    }

    private static string? ResolveInputPath(string? path, string repositoryRoot)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return null;
        }

        return Path.GetFullPath(Path.IsPathRooted(path)
            ? path
            : Path.Combine(repositoryRoot, path));
    }

    private static int CountLines(string text)
    {
        if (text.Length == 0)
        {
            return 1;
        }

        return text.Count(character => character == '\n') + 1;
    }

    private sealed record FileParseContext(
        string FullPath,
        string RelativePath,
        string Text,
        string ContentHash,
        string FileNodeId,
        SyntaxTree SyntaxTree,
        bool IsTestFile);

    private sealed record ProjectParseContext(
        string ProjectName,
        Compilation Compilation,
        IReadOnlyList<FileParseContext> Files);
}
