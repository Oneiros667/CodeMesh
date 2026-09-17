using System.Diagnostics;
using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Utilities;

namespace CodeMesh.Ingestion.Summary.Qualification;

public static class SummaryQualificationConstants
{
    public const string SchemaVersion = "1.0";
    public const string SuiteKind = "summary-qualification-suite";
    public const string ProfileKind = "summary-qualification-profile";
    public const string ArchiveKind = "summary-qualification-private-archive";
    public const string ReviewPacketKind = "summary-qualification-review-packet";
    public const string ReviewKind = "summary-qualification-review";
    public const string RetrievalAssessmentKind = "summary-qualification-retrieval-assessment";
    public const string RetrievalEvidenceKind = "summary-qualification-retrieval-evidence";
    public const string DeploymentEvidenceKind = "summary-qualification-deployment-evidence";
    public const string ReportKind = "summary-qualification-report";
}

public sealed record SummaryQualificationGates(
    double MinimumFirstAttemptSchemaRate = 0.995,
    double MinimumEventualCompletionRate = 0.999,
    int MaximumSecretCanaryLeaks = 0,
    int MaximumCriticalHallucinations = 0,
    double MinimumAtomicFactualPrecision = 0.95,
    double MinimumRequiredFactRecall = 0.80,
    double MinimumStratumRequiredFactRecall = 0.70,
    double MaximumAbsoluteRetrievalRegression = 0.01,
    int MaximumSafetyFailures = 0,
    double? MaximumP95LatencyMs = null,
    double? MinimumNodesPerMinute = null,
    long? MaximumTotalTokens = null,
    double? MaximumTokensPerSuccessfulNode = null,
    double? MaximumTotalDurationMs = null,
    double? MaximumRetryTokenOverheadRatio = null,
    double? MaximumPeakHostMemoryMb = null,
    double? MaximumPeakAcceleratorMemoryMb = null,
    decimal? MaximumOnlineCost = null);

public sealed record SummaryQualificationCorpusItem(
    string Id,
    string RepositoryId,
    string RepositoryCommit,
    string NodeId,
    string ContentHash,
    string Language,
    CodeNodeKind NodeKind,
    string Name,
    string Project,
    string FilePath,
    int StartLine,
    int EndLine,
    string Source,
    string InputSizeBand,
    string Criticality,
    IReadOnlyList<string> Strata,
    IReadOnlyList<string> RequiredFacts,
    IReadOnlyList<string> OptionalFacts,
    IReadOnlyList<string> ForbiddenClaims,
    IReadOnlyList<string> RequiredTags,
    IReadOnlyList<string> AcceptableTags,
    string Partition,
    string ExpectedResponsibility,
    IReadOnlyList<string> ImportantInputs,
    IReadOnlyList<string> ImportantOutputs,
    IReadOnlyList<string> SideEffects,
    IReadOnlyList<string> FailureBehavior,
    string ReferenceSummary,
    IReadOnlyList<string>? SecretCanaries = null);

public sealed record SummaryQualificationSuite(
    string SchemaVersion,
    string Kind,
    string Name,
    string Version,
    IReadOnlyList<SummaryQualificationCorpusItem> Items,
    SummaryQualificationGates Gates);

public sealed record SummaryQualificationProfile(
    string SchemaVersion,
    string Kind,
    string Name,
    string IntendedUse,
    string EndpointClass,
    string Provider,
    string Model,
    string ModelRevision,
    string Quantization,
    string NumericPrecision,
    string ChatTemplateHash,
    int ContextLength,
    int MaxInputCharacters,
    int ReasoningTokenReserve,
    int MaxCompletionTokens,
    int Repetitions,
    IReadOnlyDictionary<string, string> GenerationSettings,
    IReadOnlyDictionary<string, string> Host,
    IReadOnlyDictionary<string, string>? OnlinePolicy = null,
    IReadOnlyList<string>? Conditions = null);

public sealed record SummaryQualificationSourceIdentity(
    string CodeMeshCommit,
    bool WorkingTreeDirty,
    string? Branch,
    string? RemoteUrl,
    string OperatingSystem,
    string RuntimeVersion);

public sealed record SummaryQualificationRepositoryIdentity(
    string RepositoryId,
    string RepositoryCommit);

public sealed record SummaryQualificationSample(
    string SampleId,
    string ItemId,
    int Repetition,
    string Phase,
    bool Completed,
    long LatencyMs,
    string? FailureCategory,
    string? Summary,
    IReadOnlyList<string> Tags,
    string? Confidence,
    CodeSummaryUsage? Usage,
    IReadOnlyDictionary<string, string>? ProviderMetadata,
    string RedactedContentHash,
    bool InputTruncated,
    int InputCharacters);

public sealed record SummaryQualificationPrivateArchive(
    string SchemaVersion,
    string Kind,
    string RunId,
    string SuiteName,
    string SuiteVersion,
    string SuiteHash,
    string CorpusRepositoryIdentityHash,
    IReadOnlyList<SummaryQualificationRepositoryIdentity> CorpusRepositories,
    string ProfileHash,
    string ProviderGenerationConfigurationFingerprint,
    SummaryQualificationSourceIdentity SourceIdentity,
    SummaryQualificationProfile Profile,
    string PromptVersion,
    string PromptHash,
    DateTimeOffset StartedAt,
    DateTimeOffset CompletedAt,
    IReadOnlyList<SummaryQualificationSample> Samples,
    IReadOnlyList<string> PreflightFailures);

public sealed record SummaryQualificationReviewItem(
    string SampleId,
    string ItemId,
    string Source,
    IReadOnlyList<string> RequiredFacts,
    IReadOnlyList<string> OptionalFacts,
    IReadOnlyList<string> ForbiddenClaims,
    IReadOnlyList<string> RequiredTags,
    IReadOnlyList<string> AcceptableTags,
    string ExpectedResponsibility,
    IReadOnlyList<string> ImportantInputs,
    IReadOnlyList<string> ImportantOutputs,
    IReadOnlyList<string> SideEffects,
    IReadOnlyList<string> FailureBehavior,
    string ReferenceSummary,
    string? CandidateSummary,
    IReadOnlyList<string> CandidateTags,
    string? CandidateConfidence);

public sealed record SummaryQualificationReviewPacket(
    string SchemaVersion,
    string Kind,
    string RunId,
    string CandidateLabel,
    string SuiteHash,
    IReadOnlyList<SummaryQualificationReviewItem> Items);

public sealed record SummaryQualificationSampleReview(
    string SampleId,
    string ItemId,
    int SupportedFactCount,
    int GeneratedFactCount,
    int RequiredFactCount,
    int RequiredFactPresentCount,
    bool CriticalHallucination,
    bool Contradiction,
    bool PurposeAccurate,
    int BehaviorFactCount,
    int BehaviorFactPresentCount,
    int UsefulSupportedFactCount,
    bool OverallFactuallyCorrect,
    bool ConfidenceAppropriate,
    int TagTruePositiveCount,
    int TagFalsePositiveCount,
    int TagFalseNegativeCount,
    int SafetyFailureCount = 0,
    string? Limitation = null);

public sealed record SummaryQualificationReview(
    string SchemaVersion,
    string Kind,
    string RunId,
    string ReviewerId,
    bool Blinded,
    string ResolutionRecordHash,
    IReadOnlyList<SummaryQualificationSampleReview> Samples);

public sealed record SummaryRetrievalMetrics(
    double RecallAtK,
    double MeanReciprocalRank,
    double NdcgAtK,
    double PrecisionAtK,
    double RankingStability,
    int SecretLeaks,
    bool Passed,
    bool Comparable);

public sealed record SummaryQualificationRetrievalAssessment(
    string SchemaVersion,
    string Kind,
    string RunId,
    string BaselineReportHash,
    string CandidateReportHash,
    int CorrectSummaryHitContributions,
    int FalsePositiveSummaryHits,
    int QueriesImproved,
    int QueriesUnchanged,
    int QueriesDegraded,
    double BaselineContextRelevance,
    double CandidateContextRelevance,
    double BaselineContextTokenDensity,
    double CandidateContextTokenDensity,
    int UnresolvedMaterialRegressions,
    bool Reviewed);

public sealed record SummaryQualificationRetrievalEvidence(
    string SchemaVersion,
    string Kind,
    string RunId,
    string SuiteHash,
    string PromptHash,
    string CorpusRepositoryIdentityHash,
    string RankingIdentityHash,
    string LiveSuite,
    string RepositoryId,
    string RepositoryCommit,
    string BaselineReportHash,
    string CandidateReportHash,
    SummaryRetrievalMetrics Baseline,
    SummaryRetrievalMetrics Candidate,
    SummaryQualificationRetrievalAssessment Assessment,
    IReadOnlyList<string> SafetyFailures);

public sealed record SummaryQualificationDeploymentEvidence(
    string SchemaVersion,
    string Kind,
    string RunId,
    string ProfileHash,
    string MeasurementMethod,
    double PeakHostMemoryMb,
    double? PeakAcceleratorMemoryMb,
    decimal? ProviderReportedCost,
    string? PricingSnapshotHash,
    bool Complete);

public sealed record SummaryQualificationStratumMetrics(
    int SampleCount,
    double AtomicFactualPrecision,
    double RequiredFactRecall,
    double PurposeAccuracy,
    double BehaviorCoverage);

public sealed record SummaryQualificationMetrics(
    int Attempted,
    int Completed,
    double FirstAttemptSchemaRate,
    double EventualCompletionRate,
    int SecretCanaryLeaks,
    double AtomicFactualPrecision,
    double RequiredFactRecall,
    IReadOnlyDictionary<string, double> RequiredFactRecallByStratum,
    int CriticalHallucinations,
    int Contradictions,
    double PurposeAccuracy,
    double BehaviorCoverage,
    double ConfidenceCalibrationAccuracy,
    double InformationDensityPer1000OutputTokens,
    double IdenticalInputStability,
    double TagPrecision,
    double TagRecall,
    double TagF1,
    double P50LatencyMs,
    double P95LatencyMs,
    double MaximumLatencyMs,
    double WarmupLatencyMs,
    double NodesPerMinute,
    double SuccessfulNodesPerHour,
    long? InputTokens,
    long? CachedInputTokens,
    long? CacheWriteInputTokens,
    long? OutputTokens,
    long? ReasoningTokens,
    long? TotalTokens,
    double? TokensPerAttemptedNode,
    double? TokensPerSuccessfulNode,
    double RetryTokenOverheadRatio,
    double SupportedFactsPer1000OutputTokens,
    double RequiredFactsPer1000OutputTokens,
    double TotalDurationMs,
    double? PeakHostMemoryMb,
    double? PeakAcceleratorMemoryMb,
    decimal? ProviderReportedCost,
    IReadOnlyDictionary<string, SummaryQualificationStratumMetrics> ByStratum,
    SummaryRetrievalMetrics? BaselineRetrieval,
    SummaryRetrievalMetrics? CandidateRetrieval,
    SummaryQualificationRetrievalAssessment? RetrievalAssessment);

public sealed record SummaryQualificationReport(
    string SchemaVersion,
    string Kind,
    string RunId,
    string Outcome,
    string IntendedUse,
    string SuiteName,
    string SuiteVersion,
    string SuiteHash,
    string CorpusRepositoryIdentityHash,
    string ProfileHash,
    string Provider,
    string Model,
    string ModelRevision,
    string PromptVersion,
    string PromptHash,
    string ProviderGenerationConfigurationFingerprint,
    string RankingIdentityHash,
    string RetrievalSuite,
    string RetrievalRepositoryId,
    string RetrievalRepositoryCommit,
    string DeploymentEvidenceHash,
    string CodeMeshCommit,
    DateTimeOffset GeneratedAt,
    SummaryQualificationMetrics Metrics,
    IReadOnlyList<string> FailedSampleIds,
    IReadOnlyList<string> FailedGates,
    IReadOnlyList<string> InvalidReasons,
    IReadOnlyList<string> Conditions,
    IReadOnlyList<string> Limitations);

public sealed record SummaryQualificationRunResult(
    SummaryQualificationPrivateArchive PrivateArchive,
    SummaryQualificationReviewPacket ReviewPacket);

public sealed class SummaryQualificationRunner(ICodeSummaryProvider provider)
{
    public async Task<SummaryQualificationRunResult> RunAsync(
        SummaryQualificationSuite suite,
        SummaryQualificationProfile profile,
        SummaryQualificationSourceIdentity sourceIdentity,
        CancellationToken cancellationToken = default)
    {
        var preflightFailures = Validate(suite, profile, sourceIdentity, provider);
        if (preflightFailures.Count > 0)
        {
            throw new InvalidOperationException(
                $"Summary qualification preflight failed: {string.Join(" ", preflightFailures)}");
        }

        var suiteHash = Fingerprint.Suite(suite);
        var profileHash = Fingerprint.Profile(profile);
        var repositoryIdentityHash = Fingerprint.RepositoryIdentity(suite.Items);
        var promptVersion = SummaryPrompt.DefaultPromptVersion;
        var promptHash = SummaryPrompt.PromptHash(promptVersion);
        var qualificationItems = suite.Items
            .Where(item => string.Equals(item.Partition, "qualification", StringComparison.Ordinal))
            .ToArray();
        var warmupItem = suite.Items.First(item => string.Equals(item.Partition, "calibration", StringComparison.Ordinal));
        var runId = CodeMeshHash.StableId(
            "summary-qualification-run-v1",
            sourceIdentity.CodeMeshCommit,
            suiteHash,
            profileHash,
            promptHash,
            provider.GenerationConfigurationFingerprint,
            DateTimeOffset.UtcNow.ToString("O", System.Globalization.CultureInfo.InvariantCulture));
        var startedAt = DateTimeOffset.UtcNow;
        var samples = new List<SummaryQualificationSample>((qualificationItems.Length * profile.Repetitions) + 1);

        async Task<SummaryQualificationSample> ExecuteSampleAsync(
            SummaryQualificationCorpusItem item,
            int repetition,
            string phase)
        {
            var redactedSource = ContentRedactor.RedactText(item.Source);
            var redactedHash = CodeMeshHash.Sha256Hex(redactedSource);
            var node = CreateNode(item, redactedHash);
            var content = new CodeContent(
                redactedHash,
                redactedSource,
                "text/plain",
                startedAt,
                startedAt);
            cancellationToken.ThrowIfCancellationRequested();
            var request = SummaryBudgetPolicy.CreateRequest(
                node,
                content,
                promptVersion,
                new SummaryBudgetPolicyOptions(
                    profile.MaxInputCharacters,
                    profile.ReasoningTokenReserve,
                    profile.MaxCompletionTokens));
            var sampleId = CodeMeshHash.StableId(
                runId,
                item.Id,
                phase,
                repetition.ToString(System.Globalization.CultureInfo.InvariantCulture));
            var stopwatch = Stopwatch.StartNew();
            try
            {
                var result = await provider.SummarizeAsync(request, cancellationToken).ConfigureAwait(false);
                ValidateProviderResult(result);
                stopwatch.Stop();
                return new SummaryQualificationSample(
                    sampleId,
                    item.Id,
                    repetition,
                    phase,
                    true,
                    stopwatch.ElapsedMilliseconds,
                    null,
                    result.Summary,
                    result.Tags,
                    result.Confidence,
                    result.Usage,
                    result.ProviderMetadata,
                    redactedHash,
                    request.Budget?.InputTruncated ?? false,
                    request.Budget?.InputCharacters ?? 0);
            }
            catch (Exception exception) when (exception is not OperationCanceledException)
            {
                stopwatch.Stop();
                return new SummaryQualificationSample(
                    sampleId,
                    item.Id,
                    repetition,
                    phase,
                    false,
                    stopwatch.ElapsedMilliseconds,
                    FailureCategory(exception),
                    null,
                    [],
                    null,
                    null,
                    null,
                    redactedHash,
                    request.Budget?.InputTruncated ?? false,
                    request.Budget?.InputCharacters ?? 0);
            }
        }

        var runtimeFailures = new List<string>();
        var warmup = await ExecuteSampleAsync(warmupItem, 0, "warmup").ConfigureAwait(false);
        samples.Add(warmup);
        if (!warmup.Completed)
        {
            runtimeFailures.Add($"Warm-up failed with category '{warmup.FailureCategory ?? "unknown"}'; measured repetitions were not started.");
        }
        else
        {
            foreach (var item in qualificationItems)
            {
                for (var repetition = 1; repetition <= profile.Repetitions; repetition++)
                {
                    samples.Add(await ExecuteSampleAsync(item, repetition, "measured").ConfigureAwait(false));
                }
            }
        }

        var archive = new SummaryQualificationPrivateArchive(
            SummaryQualificationConstants.SchemaVersion,
            SummaryQualificationConstants.ArchiveKind,
            runId,
            suite.Name,
            suite.Version,
            suiteHash,
            repositoryIdentityHash,
            suite.Items
                .Select(item => new SummaryQualificationRepositoryIdentity(item.RepositoryId, item.RepositoryCommit))
                .Distinct()
                .OrderBy(item => item.RepositoryId, StringComparer.Ordinal)
                .ThenBy(item => item.RepositoryCommit, StringComparer.Ordinal)
                .ToArray(),
            profileHash,
            provider.GenerationConfigurationFingerprint,
            sourceIdentity,
            profile,
            promptVersion,
            promptHash,
            startedAt,
            DateTimeOffset.UtcNow,
            samples,
            runtimeFailures);
        var itemsById = suite.Items.ToDictionary(item => item.Id, StringComparer.Ordinal);
        var packet = new SummaryQualificationReviewPacket(
            SummaryQualificationConstants.SchemaVersion,
            SummaryQualificationConstants.ReviewPacketKind,
            runId,
            $"candidate-{runId[..12]}",
            suiteHash,
            samples
                .Where(sample => string.Equals(sample.Phase, "measured", StringComparison.Ordinal))
                .Select(sample => CreateReviewItem(sample, itemsById[sample.ItemId]))
                .ToArray());

        return new SummaryQualificationRunResult(archive, packet);
    }

    public static async Task<SummaryQualificationSourceIdentity> CaptureSourceIdentityAsync(
        string codeMeshRoot,
        CancellationToken cancellationToken = default)
    {
        var snapshot = await RepositoryGitSnapshot.CaptureAsync(codeMeshRoot, cancellationToken).ConfigureAwait(false);
        return new SummaryQualificationSourceIdentity(
            snapshot.Commit ?? string.Empty,
            snapshot.WorkingTreeDirty,
            snapshot.Branch,
            snapshot.RemoteUrl,
            System.Runtime.InteropServices.RuntimeInformation.OSDescription,
            System.Runtime.InteropServices.RuntimeInformation.FrameworkDescription);
    }

    private static List<string> Validate(
        SummaryQualificationSuite suite,
        SummaryQualificationProfile profile,
        SummaryQualificationSourceIdentity sourceIdentity,
        ICodeSummaryProvider candidate)
    {
        var failures = new List<string>();
        if (!string.Equals(suite.SchemaVersion, SummaryQualificationConstants.SchemaVersion, StringComparison.Ordinal) ||
            !string.Equals(suite.Kind, SummaryQualificationConstants.SuiteKind, StringComparison.Ordinal))
        {
            failures.Add("Unsupported suite schema or kind.");
        }

        if (!string.Equals(profile.SchemaVersion, SummaryQualificationConstants.SchemaVersion, StringComparison.Ordinal) ||
            !string.Equals(profile.Kind, SummaryQualificationConstants.ProfileKind, StringComparison.Ordinal))
        {
            failures.Add("Unsupported deployment-profile schema or kind.");
        }

        if (suite.Items.Count == 0 || suite.Items.Select(item => item.Id).Distinct(StringComparer.Ordinal).Count() != suite.Items.Count)
        {
            failures.Add("The suite must contain uniquely identified corpus items.");
        }

        if (!suite.Items.Any(item => string.Equals(item.Partition, "calibration", StringComparison.Ordinal)) ||
            !suite.Items.Any(item => string.Equals(item.Partition, "qualification", StringComparison.Ordinal)))
        {
            failures.Add("The suite must contain separate calibration and held-out qualification partitions.");
        }

        foreach (var item in suite.Items)
        {
            if (string.IsNullOrWhiteSpace(item.RepositoryCommit) ||
                string.IsNullOrWhiteSpace(item.ContentHash) ||
                !string.Equals(CodeMeshHash.Sha256Hex(item.Source), item.ContentHash, StringComparison.Ordinal))
            {
                failures.Add($"Corpus item '{item.Id}' has incomplete or mismatched immutable source identity.");
            }

            if (string.IsNullOrWhiteSpace(item.Id) ||
                string.IsNullOrWhiteSpace(item.NodeId) ||
                string.IsNullOrWhiteSpace(item.Language) ||
                string.IsNullOrWhiteSpace(item.FilePath) ||
                string.IsNullOrWhiteSpace(item.ExpectedResponsibility) ||
                string.IsNullOrWhiteSpace(item.ReferenceSummary) ||
                item.RequiredFacts.Count == 0 ||
                item.Strata.Count == 0 ||
                item.NodeKind == CodeNodeKind.Unknown ||
                item.Partition is not ("calibration" or "qualification"))
            {
                failures.Add($"Corpus item '{item.Id}' is missing required labels, strata, or node identity.");
            }

            if (RepositoryPathPolicy.IsIgnoredRelativePath(item.FilePath))
            {
                failures.Add($"Corpus item '{item.Id}' uses a generated, cache, or known-secret file path.");
            }

            if ((item.SecretCanaries ?? []).Any(canary =>
                    string.IsNullOrWhiteSpace(canary) ||
                    !item.Source.Contains(canary, StringComparison.Ordinal)))
            {
                failures.Add($"Corpus item '{item.Id}' declares a missing or empty secret canary.");
            }
        }

        if (string.IsNullOrWhiteSpace(sourceIdentity.CodeMeshCommit) || sourceIdentity.WorkingTreeDirty)
        {
            failures.Add("CodeMesh must be at a recorded clean commit.");
        }

        if (!string.Equals(profile.Provider, candidate.Provider, StringComparison.OrdinalIgnoreCase) ||
            !string.Equals(profile.Model, candidate.Model, StringComparison.Ordinal))
        {
            failures.Add("The deployment profile does not match the configured provider and model.");
        }

        if (string.IsNullOrWhiteSpace(candidate.GenerationConfigurationFingerprint) ||
            !profile.GenerationSettings.TryGetValue("providerGenerationConfigurationFingerprint", out var expectedConfiguration) ||
            !string.Equals(expectedConfiguration, candidate.GenerationConfigurationFingerprint, StringComparison.Ordinal))
        {
            failures.Add("The deployment profile does not match the provider's effective generation configuration fingerprint.");
        }

        if (!profile.GenerationSettings.TryGetValue("retryPolicy", out var retryPolicy) ||
            !string.Equals(retryPolicy, "none", StringComparison.Ordinal))
        {
            failures.Add("Qualification runner v1 supports only an explicit retryPolicy of 'none'.");
        }

        RequireKeys(
            failures,
            "generation settings",
            profile.GenerationSettings,
            [
                "providerGenerationConfigurationFingerprint",
                "temperature",
                "topP",
                "topK",
                "seed",
                "stopSequences",
                "requestedReasoningEffort",
                "effectiveReasoningEffort",
                "retryPolicy",
                "timeout",
                "concurrency",
                "batching"
            ]);
        RequireKeys(
            failures,
            "host identity",
            profile.Host,
            [
                "operatingSystem",
                "cpu",
                "memory",
                "accelerator",
                "acceleratorMemory",
                "servingRuntime"
            ]);

        if (string.IsNullOrWhiteSpace(profile.Name) ||
            string.IsNullOrWhiteSpace(profile.ModelRevision) ||
            string.IsNullOrWhiteSpace(profile.Quantization) ||
            string.IsNullOrWhiteSpace(profile.NumericPrecision) ||
            string.IsNullOrWhiteSpace(profile.ChatTemplateHash) ||
            profile.Host.Count == 0)
        {
            failures.Add("The deployment profile is missing model-build, template, precision, or host identity.");
        }

        if (profile.Repetitions < 3)
        {
            failures.Add("At least three measured repetitions are required.");
        }

        if (profile.MaxInputCharacters < 512 || profile.MaxCompletionTokens < 448 || profile.ContextLength <= 0)
        {
            failures.Add("The deployment profile has invalid context or token budgets.");
        }

        var intendedUses = new[] { "local-offline", "private-network", "online-approved-data" };
        if (!intendedUses.Contains(profile.IntendedUse, StringComparer.Ordinal))
        {
            failures.Add("The intended use is not recognized.");
        }

        var endpointClasses = new[] { "local", "private-network", "online" };
        if (!endpointClasses.Contains(profile.EndpointClass, StringComparer.Ordinal))
        {
            failures.Add("The endpoint class is not recognized.");
        }

        if (string.Equals(profile.EndpointClass, "online", StringComparison.Ordinal) &&
            !string.Equals(profile.IntendedUse, "online-approved-data", StringComparison.Ordinal))
        {
            failures.Add("An online endpoint can only be evaluated for online-approved-data use.");
        }

        if (string.Equals(profile.EndpointClass, "local", StringComparison.Ordinal) &&
            (!profile.Host.TryGetValue("operatingSystem", out var profileOperatingSystem) ||
             !string.Equals(profileOperatingSystem, sourceIdentity.OperatingSystem, StringComparison.Ordinal)))
        {
            failures.Add("A local deployment profile must match the captured host operating-system identity.");
        }

        if (string.Equals(profile.IntendedUse, "online-approved-data", StringComparison.Ordinal) &&
            (profile.OnlinePolicy is null || profile.OnlinePolicy.Count == 0))
        {
            failures.Add("Online qualification requires a recorded governance and pricing policy snapshot.");
        }
        else if (string.Equals(profile.IntendedUse, "online-approved-data", StringComparison.Ordinal))
        {
            RequireKeys(
                failures,
                "online policy",
                profile.OnlinePolicy!,
                ["apiVersion", "serviceRegion", "retentionPolicy", "pricingSnapshotHash", "maximumCost"]);
        }

        return failures;
    }

    private static CodeNode CreateNode(SummaryQualificationCorpusItem item, string redactedHash)
    {
        return new CodeNode(
            item.NodeId,
            $"qualification:{item.RepositoryId}:{item.NodeId}",
            item.NodeKind,
            item.Name,
            item.Language,
            item.Project,
            new SourceSpan(item.FilePath, item.StartLine, 1, item.EndLine, 1),
            redactedHash,
            new Dictionary<string, string>(StringComparer.Ordinal)
            {
                ["summaryQualificationItemId"] = item.Id,
                ["summaryQualificationCriticality"] = item.Criticality
            });
    }

    private static void RequireKeys(
        List<string> failures,
        string label,
        IReadOnlyDictionary<string, string> values,
        IReadOnlyList<string> requiredKeys)
    {
        var missing = requiredKeys
            .Where(key => !values.TryGetValue(key, out var value) || string.IsNullOrWhiteSpace(value))
            .ToArray();
        if (missing.Length > 0)
        {
            failures.Add($"The deployment profile {label} are missing: {string.Join(", ", missing)}.");
        }
    }

    private static SummaryQualificationReviewItem CreateReviewItem(
        SummaryQualificationSample sample,
        SummaryQualificationCorpusItem item)
    {
        return new SummaryQualificationReviewItem(
            sample.SampleId,
            item.Id,
            ContentRedactor.RedactText(item.Source),
            item.RequiredFacts,
            item.OptionalFacts,
            item.ForbiddenClaims,
            item.RequiredTags,
            item.AcceptableTags,
            item.ExpectedResponsibility,
            item.ImportantInputs,
            item.ImportantOutputs,
            item.SideEffects,
            item.FailureBehavior,
            item.ReferenceSummary,
            sample.Summary,
            sample.Tags,
            sample.Confidence);
    }

    private static string FailureCategory(Exception exception)
    {
        return exception switch
        {
            TimeoutException or TaskCanceledException => "timeout",
            HttpRequestException => "provider-transport",
            InvalidOperationException when exception.Message.Contains("JSON", StringComparison.OrdinalIgnoreCase) => "schema-invalid",
            InvalidOperationException when exception.Message.Contains("empty", StringComparison.OrdinalIgnoreCase) => "empty-response",
            _ => "provider-error"
        };
    }

    private static void ValidateProviderResult(CodeSummaryResult result)
    {
        if (string.IsNullOrWhiteSpace(result.Summary) ||
            result.Tags is null ||
            result.Tags.Count > 8 ||
            result.Tags.Any(string.IsNullOrWhiteSpace) ||
            result.Confidence is not ("high" or "medium" or "low"))
        {
            throw new InvalidOperationException("Summary provider result violated the production JSON contract.");
        }

        if (result.Usage is { } usage &&
            (usage.InputTokens < 0 ||
             usage.CachedInputTokens < 0 ||
             usage.CacheWriteInputTokens < 0 ||
             usage.OutputTokens < 0 ||
             usage.ReasoningTokens < 0 ||
             usage.TotalTokens < 0))
        {
            throw new InvalidOperationException("Summary provider returned invalid usage counts.");
        }
    }
}

public static class SummaryQualificationCompiler
{
    public static SummaryQualificationReport Compile(
        SummaryQualificationSuite suite,
        SummaryQualificationPrivateArchive archive,
        IReadOnlyList<SummaryQualificationReview> reviews,
        SummaryQualificationRetrievalEvidence? retrievalEvidence,
        SummaryQualificationDeploymentEvidence? deploymentEvidence)
    {
        var invalid = ValidateInputs(suite, archive, reviews, retrievalEvidence, deploymentEvidence);
        var measured = archive.Samples
            .Where(sample => string.Equals(sample.Phase, "measured", StringComparison.Ordinal))
            .ToArray();
        var completed = measured.Where(sample => sample.Completed).ToArray();
        var sampleReviews = MergeReviews(suite, completed, reviews, invalid);
        var canariesByItem = suite.Items.ToDictionary(
            item => item.Id,
            item => item.SecretCanaries ?? [],
            StringComparer.Ordinal);
        var canaryLeaks = completed.Sum(sample => CountCanaryLeaks(sample, canariesByItem[sample.ItemId]));
        var generatedFacts = sampleReviews.Sum(review => review.GeneratedFactCount);
        var supportedFacts = sampleReviews.Sum(review => review.SupportedFactCount);
        var requiredFacts = sampleReviews.Sum(review => review.RequiredFactCount);
        var presentFacts = sampleReviews.Sum(review => review.RequiredFactPresentCount);
        var behaviorFacts = sampleReviews.Sum(review => review.BehaviorFactCount);
        var presentBehaviorFacts = sampleReviews.Sum(review => review.BehaviorFactPresentCount);
        var usefulSupportedFacts = sampleReviews.Sum(review => review.UsefulSupportedFactCount);
        var strata = RequiredRecallByStratum(suite, sampleReviews);
        var elapsedMs = Math.Max(1, measured.Sum(sample => sample.LatencyMs));
        var totalDurationMs = Math.Max(1, (archive.CompletedAt - archive.StartedAt).TotalMilliseconds);
        var usageComplete = archive.Samples.Count > 0 && archive.Samples.All(sample => sample.Usage is not null);
        long? inputTokens = usageComplete ? archive.Samples.Sum(sample => (long)sample.Usage!.InputTokens) : null;
        long? cachedInputTokens = usageComplete ? archive.Samples.Sum(sample => (long)sample.Usage!.CachedInputTokens) : null;
        long? cacheWriteInputTokens = usageComplete ? archive.Samples.Sum(sample => (long)sample.Usage!.CacheWriteInputTokens) : null;
        long? outputTokens = usageComplete ? archive.Samples.Sum(sample => (long)sample.Usage!.OutputTokens) : null;
        long? reasoningTokens = usageComplete ? archive.Samples.Sum(sample => (long)sample.Usage!.ReasoningTokens) : null;
        long? totalTokens = usageComplete ? archive.Samples.Sum(sample => (long)sample.Usage!.TotalTokens) : null;
        var measuredOutputTokens = measured.Length > 0 && measured.All(sample => sample.Usage is not null)
            ? measured.Sum(sample => (long)sample.Usage!.OutputTokens)
            : (long?)null;
        var successfulAttempts = archive.Samples.Count(sample => sample.Completed);
        var metrics = new SummaryQualificationMetrics(
            measured.Length,
            completed.Length,
            Rate(completed.Length, measured.Length),
            Rate(completed.Length, measured.Length),
            canaryLeaks,
            Rate(supportedFacts, generatedFacts),
            Rate(presentFacts, requiredFacts),
            strata,
            sampleReviews.Count(review => review.CriticalHallucination),
            sampleReviews.Count(review => review.Contradiction),
            Rate(sampleReviews.Count(review => review.PurposeAccurate), sampleReviews.Count),
            Rate(presentBehaviorFacts, behaviorFacts),
            Rate(sampleReviews.Count(review => review.ConfidenceAppropriate), sampleReviews.Count),
            PerThousand(usefulSupportedFacts, measuredOutputTokens),
            IdenticalInputStability(measured, archive.Profile.Repetitions),
            Rate(sampleReviews.Sum(review => review.TagTruePositiveCount), sampleReviews.Sum(review => review.TagTruePositiveCount + review.TagFalsePositiveCount)),
            Rate(sampleReviews.Sum(review => review.TagTruePositiveCount), sampleReviews.Sum(review => review.TagTruePositiveCount + review.TagFalseNegativeCount)),
            0,
            Percentile(measured.Select(sample => (double)sample.LatencyMs), 0.50),
            Percentile(measured.Select(sample => (double)sample.LatencyMs), 0.95),
            measured.Length == 0 ? 0 : measured.Max(sample => (double)sample.LatencyMs),
            archive.Samples.FirstOrDefault(sample => string.Equals(sample.Phase, "warmup", StringComparison.Ordinal))?.LatencyMs ?? 0,
            completed.Length / (elapsedMs / 60000d),
            completed.Length / (elapsedMs / 3600000d),
            inputTokens,
            cachedInputTokens,
            cacheWriteInputTokens,
            outputTokens,
            reasoningTokens,
            totalTokens,
            totalTokens is null || archive.Samples.Count == 0 ? null : totalTokens.Value / (double)archive.Samples.Count,
            totalTokens is null || successfulAttempts == 0 ? null : totalTokens.Value / (double)successfulAttempts,
            0,
            PerThousand(supportedFacts, measuredOutputTokens),
            PerThousand(presentFacts, measuredOutputTokens),
            totalDurationMs,
            deploymentEvidence?.PeakHostMemoryMb,
            deploymentEvidence?.PeakAcceleratorMemoryMb,
            deploymentEvidence?.ProviderReportedCost,
            MetricsByStratum(suite, sampleReviews),
            retrievalEvidence?.Baseline,
            retrievalEvidence?.Candidate,
            retrievalEvidence?.Assessment);
        var tagF1 = HarmonicMean(metrics.TagPrecision, metrics.TagRecall);
        metrics = metrics with { TagF1 = tagF1 };

        var failed = invalid.Count == 0
            ? FailedGates(suite.Gates, metrics, sampleReviews, retrievalEvidence, deploymentEvidence)
            : [];
        var outcome = invalid.Count > 0
            ? "invalid-run"
            : failed.Count > 0
                ? "not-qualified"
                : archive.Profile.Conditions is { Count: > 0 }
                    ? "conditionally-qualified"
                    : "qualified";
        var limitations = sampleReviews
            .Where(review => !string.IsNullOrWhiteSpace(review.Limitation))
            .Select(review => $"Reviewer limitation recorded for sample {review.SampleId}.")
            .Distinct(StringComparer.Ordinal)
            .ToArray();
        var failedSampleIds = measured
            .Where(sample => !sample.Completed)
            .Select(sample => sample.SampleId)
            .Concat(sampleReviews
                .Where(review =>
                    review.CriticalHallucination ||
                    review.Contradiction ||
                    !review.PurposeAccurate ||
                    !review.OverallFactuallyCorrect ||
                    !review.ConfidenceAppropriate ||
                    review.SafetyFailureCount > 0 ||
                    review.SupportedFactCount < review.GeneratedFactCount ||
                    review.RequiredFactPresentCount < review.RequiredFactCount ||
                    review.BehaviorFactPresentCount < review.BehaviorFactCount)
                .Select(review => review.SampleId))
            .Distinct(StringComparer.Ordinal)
            .ToArray();

        return new SummaryQualificationReport(
            SummaryQualificationConstants.SchemaVersion,
            SummaryQualificationConstants.ReportKind,
            archive.RunId,
            outcome,
            archive.Profile.IntendedUse,
            archive.SuiteName,
            archive.SuiteVersion,
            archive.SuiteHash,
            archive.CorpusRepositoryIdentityHash,
            archive.ProfileHash,
            archive.Profile.Provider,
            archive.Profile.Model,
            archive.Profile.ModelRevision,
            archive.PromptVersion,
            archive.PromptHash,
            archive.ProviderGenerationConfigurationFingerprint,
            retrievalEvidence?.RankingIdentityHash ?? string.Empty,
            retrievalEvidence?.LiveSuite ?? string.Empty,
            retrievalEvidence?.RepositoryId ?? string.Empty,
            retrievalEvidence?.RepositoryCommit ?? string.Empty,
            deploymentEvidence is null
                ? string.Empty
                : CodeMeshHash.Sha256Hex(System.Text.Json.JsonSerializer.Serialize(deploymentEvidence)),
            archive.SourceIdentity.CodeMeshCommit,
            DateTimeOffset.UtcNow,
            metrics,
            failedSampleIds,
            failed,
            invalid,
            archive.Profile.Conditions ?? [],
            limitations);
    }

    public static IReadOnlyDictionary<string, double> Compare(
        SummaryQualificationReport candidate,
        SummaryQualificationReport reference)
    {
        if (!string.Equals(candidate.SuiteHash, reference.SuiteHash, StringComparison.Ordinal) ||
            !string.Equals(candidate.PromptHash, reference.PromptHash, StringComparison.Ordinal) ||
            !string.Equals(candidate.CorpusRepositoryIdentityHash, reference.CorpusRepositoryIdentityHash, StringComparison.Ordinal) ||
            !string.Equals(candidate.RankingIdentityHash, reference.RankingIdentityHash, StringComparison.Ordinal) ||
            !string.Equals(candidate.RetrievalSuite, reference.RetrievalSuite, StringComparison.Ordinal) ||
            !string.Equals(candidate.RetrievalRepositoryId, reference.RetrievalRepositoryId, StringComparison.Ordinal) ||
            !string.Equals(candidate.RetrievalRepositoryCommit, reference.RetrievalRepositoryCommit, StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "Qualification reports have incompatible corpus, prompt, repository, or ranking identities.");
        }

        return new Dictionary<string, double>(StringComparer.Ordinal)
        {
            ["firstAttemptSchemaRate"] = candidate.Metrics.FirstAttemptSchemaRate - reference.Metrics.FirstAttemptSchemaRate,
            ["atomicFactualPrecision"] = candidate.Metrics.AtomicFactualPrecision - reference.Metrics.AtomicFactualPrecision,
            ["requiredFactRecall"] = candidate.Metrics.RequiredFactRecall - reference.Metrics.RequiredFactRecall,
            ["purposeAccuracy"] = candidate.Metrics.PurposeAccuracy - reference.Metrics.PurposeAccuracy,
            ["tagF1"] = candidate.Metrics.TagF1 - reference.Metrics.TagF1,
            ["p95LatencyMs"] = candidate.Metrics.P95LatencyMs - reference.Metrics.P95LatencyMs,
            ["nodesPerMinute"] = candidate.Metrics.NodesPerMinute - reference.Metrics.NodesPerMinute
        };
    }

    private static List<string> ValidateInputs(
        SummaryQualificationSuite suite,
        SummaryQualificationPrivateArchive archive,
        IReadOnlyList<SummaryQualificationReview> reviews,
        SummaryQualificationRetrievalEvidence? retrieval,
        SummaryQualificationDeploymentEvidence? deployment)
    {
        var invalid = new List<string>();
        if (!string.Equals(archive.SchemaVersion, SummaryQualificationConstants.SchemaVersion, StringComparison.Ordinal) ||
            !string.Equals(archive.Kind, SummaryQualificationConstants.ArchiveKind, StringComparison.Ordinal))
        {
            invalid.Add("Unsupported private-archive schema or kind.");
        }

        if (!string.Equals(archive.SuiteHash, Fingerprint.Suite(suite), StringComparison.Ordinal))
        {
            invalid.Add("The private archive does not match the supplied suite.");
        }

        var expectedRepositoryIdentity = Fingerprint.RepositoryIdentity(suite.Items);
        var expectedRepositories = suite.Items
            .Select(item => $"{item.RepositoryId}\u001e{item.RepositoryCommit}")
            .Distinct(StringComparer.Ordinal)
            .Order(StringComparer.Ordinal)
            .ToArray();
        var archivedRepositories = archive.CorpusRepositories
            .Select(item => $"{item.RepositoryId}\u001e{item.RepositoryCommit}")
            .Distinct(StringComparer.Ordinal)
            .Order(StringComparer.Ordinal)
            .ToArray();
        if (!string.Equals(archive.CorpusRepositoryIdentityHash, expectedRepositoryIdentity, StringComparison.Ordinal) ||
            !expectedRepositories.SequenceEqual(archivedRepositories, StringComparer.Ordinal))
        {
            invalid.Add("The private archive corpus-repository identity is incomplete or mismatched.");
        }

        if (archive.SourceIdentity.WorkingTreeDirty || string.IsNullOrWhiteSpace(archive.SourceIdentity.CodeMeshCommit))
        {
            invalid.Add("The CodeMesh source identity is not a clean recorded commit.");
        }

        if (archive.PreflightFailures.Count > 0)
        {
            invalid.AddRange(archive.PreflightFailures);
        }

        if (suite.Gates.MaximumP95LatencyMs is null ||
            suite.Gates.MinimumNodesPerMinute is null ||
            suite.Gates.MaximumTotalTokens is null ||
            suite.Gates.MaximumTokensPerSuccessfulNode is null ||
            suite.Gates.MaximumTotalDurationMs is null ||
            suite.Gates.MaximumRetryTokenOverheadRatio is null)
        {
            invalid.Add("A qualification suite must predeclare duration, latency, throughput, token, and retry-overhead deployment budgets.");
        }

        if (string.Equals(archive.Profile.EndpointClass, "online", StringComparison.Ordinal))
        {
            if (suite.Gates.MaximumOnlineCost is null)
            {
                invalid.Add("An online qualification suite must predeclare a maximum provider cost.");
            }
        }
        else
        {
            if (suite.Gates.MaximumPeakHostMemoryMb is null)
            {
                invalid.Add("A local or private-network qualification suite must predeclare a peak host-memory budget.");
            }

            var accelerator = archive.Profile.Host.GetValueOrDefault("accelerator");
            if (!string.Equals(accelerator, "none", StringComparison.OrdinalIgnoreCase) &&
                suite.Gates.MaximumPeakAcceleratorMemoryMb is null)
            {
                invalid.Add("An accelerated qualification suite must predeclare a peak accelerator-memory budget.");
            }
        }

        if (reviews.Count < 2)
        {
            invalid.Add("At least two blinded reviewer files are required.");
        }

        foreach (var review in reviews)
        {
            if (!string.Equals(review.RunId, archive.RunId, StringComparison.Ordinal) ||
                !string.Equals(review.SchemaVersion, SummaryQualificationConstants.SchemaVersion, StringComparison.Ordinal) ||
                !string.Equals(review.Kind, SummaryQualificationConstants.ReviewKind, StringComparison.Ordinal) ||
                !review.Blinded)
            {
                invalid.Add($"Reviewer '{review.ReviewerId}' is not a compatible blinded review.");
            }
        }

        var resolutionHashes = reviews
            .Select(review => review.ResolutionRecordHash)
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .Distinct(StringComparer.Ordinal)
            .ToArray();
        if (resolutionHashes.Length != 1 || reviews.Any(review => string.IsNullOrWhiteSpace(review.ResolutionRecordHash)))
        {
            invalid.Add("Blinded reviews must bind the same non-empty disagreement-resolution record hash.");
        }

        if (retrieval is null)
        {
            invalid.Add("Bound no-summary and candidate live-retrieval evidence is required.");
        }
        else if (!string.Equals(retrieval.SchemaVersion, SummaryQualificationConstants.SchemaVersion, StringComparison.Ordinal) ||
                 !string.Equals(retrieval.Kind, SummaryQualificationConstants.RetrievalEvidenceKind, StringComparison.Ordinal) ||
                 !string.Equals(retrieval.RunId, archive.RunId, StringComparison.Ordinal) ||
                 !string.Equals(retrieval.SuiteHash, archive.SuiteHash, StringComparison.Ordinal) ||
                 !string.Equals(retrieval.PromptHash, archive.PromptHash, StringComparison.Ordinal) ||
                 !string.Equals(retrieval.CorpusRepositoryIdentityHash, archive.CorpusRepositoryIdentityHash, StringComparison.Ordinal) ||
                 string.IsNullOrWhiteSpace(retrieval.RankingIdentityHash) ||
                 string.IsNullOrWhiteSpace(retrieval.LiveSuite) ||
                 !archive.CorpusRepositories.Any(repository =>
                     string.Equals(repository.RepositoryId, retrieval.RepositoryId, StringComparison.Ordinal) &&
                     string.Equals(repository.RepositoryCommit, retrieval.RepositoryCommit, StringComparison.Ordinal)) ||
                 string.IsNullOrWhiteSpace(retrieval.BaselineReportHash) ||
                 string.IsNullOrWhiteSpace(retrieval.CandidateReportHash) ||
                 string.Equals(retrieval.BaselineReportHash, retrieval.CandidateReportHash, StringComparison.Ordinal) ||
                 !string.Equals(retrieval.Assessment.SchemaVersion, SummaryQualificationConstants.SchemaVersion, StringComparison.Ordinal) ||
                 !string.Equals(retrieval.Assessment.Kind, SummaryQualificationConstants.RetrievalAssessmentKind, StringComparison.Ordinal) ||
                 !string.Equals(retrieval.Assessment.RunId, archive.RunId, StringComparison.Ordinal) ||
                 !string.Equals(retrieval.Assessment.BaselineReportHash, retrieval.BaselineReportHash, StringComparison.Ordinal) ||
                 !string.Equals(retrieval.Assessment.CandidateReportHash, retrieval.CandidateReportHash, StringComparison.Ordinal) ||
                 !retrieval.Assessment.Reviewed ||
                 HasInvalidRetrievalAssessmentCounts(retrieval.Assessment))
        {
            invalid.Add("Live-retrieval evidence is incomplete or bound to a different qualification identity.");
        }

        if (deployment is null)
        {
            invalid.Add("Bound deployment resource or cost evidence is required.");
        }
        else if (!string.Equals(deployment.SchemaVersion, SummaryQualificationConstants.SchemaVersion, StringComparison.Ordinal) ||
                 !string.Equals(deployment.Kind, SummaryQualificationConstants.DeploymentEvidenceKind, StringComparison.Ordinal) ||
                 !string.Equals(deployment.RunId, archive.RunId, StringComparison.Ordinal) ||
                 !string.Equals(deployment.ProfileHash, archive.ProfileHash, StringComparison.Ordinal) ||
                 string.IsNullOrWhiteSpace(deployment.MeasurementMethod) ||
                 deployment.PeakHostMemoryMb < 0 ||
                 deployment.PeakAcceleratorMemoryMb < 0 ||
                 deployment.ProviderReportedCost < 0 ||
                 !deployment.Complete)
        {
            invalid.Add("Deployment resource or cost evidence is incomplete or bound to a different qualification identity.");
        }
        else if (string.Equals(archive.Profile.EndpointClass, "online", StringComparison.Ordinal) &&
                 (deployment.ProviderReportedCost is null ||
                  string.IsNullOrWhiteSpace(deployment.PricingSnapshotHash) ||
                  !string.Equals(
                      deployment.PricingSnapshotHash,
                      archive.Profile.OnlinePolicy?.GetValueOrDefault("pricingSnapshotHash"),
                      StringComparison.Ordinal)))
        {
            invalid.Add("Online deployment evidence must include provider cost bound to the profile pricing snapshot.");
        }
        else if (!string.Equals(archive.Profile.EndpointClass, "online", StringComparison.Ordinal) &&
                 (deployment.PeakHostMemoryMb <= 0 ||
                  (!string.Equals(archive.Profile.Host.GetValueOrDefault("accelerator"), "none", StringComparison.OrdinalIgnoreCase) &&
                   deployment.PeakAcceleratorMemoryMb is null)))
        {
            invalid.Add("Local or private-network deployment evidence must include host and applicable accelerator memory measurements.");
        }

        return invalid;
    }

    private static bool HasInvalidRetrievalAssessmentCounts(SummaryQualificationRetrievalAssessment assessment)
    {
        return assessment.CorrectSummaryHitContributions < 0 ||
            assessment.FalsePositiveSummaryHits < 0 ||
            assessment.QueriesImproved < 0 ||
            assessment.QueriesUnchanged < 0 ||
            assessment.QueriesDegraded < 0 ||
            assessment.UnresolvedMaterialRegressions < 0 ||
            assessment.BaselineContextRelevance is < 0 or > 1 ||
            assessment.CandidateContextRelevance is < 0 or > 1 ||
            assessment.BaselineContextTokenDensity < 0 ||
            assessment.CandidateContextTokenDensity < 0 ||
            assessment.QueriesImproved + assessment.QueriesUnchanged + assessment.QueriesDegraded == 0;
    }

    private static IReadOnlyList<SummaryQualificationSampleReview> MergeReviews(
        SummaryQualificationSuite suite,
        IReadOnlyList<SummaryQualificationSample> completed,
        IReadOnlyList<SummaryQualificationReview> reviews,
        List<string> invalid)
    {
        if (reviews.Count == 0)
        {
            return [];
        }

        var completedIds = completed.Select(sample => sample.SampleId).ToHashSet(StringComparer.Ordinal);
        var reviewerIds = reviews.Select(review => review.ReviewerId).ToArray();
        if (reviewerIds.Distinct(StringComparer.Ordinal).Count() != reviewerIds.Length)
        {
            invalid.Add("Reviewer identifiers must be unique.");
        }

        foreach (var review in reviews)
        {
            var ids = review.Samples.Select(sample => sample.SampleId).ToArray();
            if (ids.Distinct(StringComparer.Ordinal).Count() != ids.Length ||
                ids.Any(id => !completedIds.Contains(id)) ||
                completedIds.Any(id => !ids.Contains(id, StringComparer.Ordinal)))
            {
                invalid.Add($"Reviewer '{review.ReviewerId}' did not score every completed sample exactly once.");
            }
        }

        if (invalid.Count > 0)
        {
            return [];
        }

        var merged = new List<SummaryQualificationSampleReview>(completed.Count);
        var itemsById = suite.Items.ToDictionary(item => item.Id, StringComparer.Ordinal);
        foreach (var sample in completed)
        {
            var scores = reviews
                .Select(review => review.Samples.Single(score => string.Equals(score.SampleId, sample.SampleId, StringComparison.Ordinal)))
                .ToArray();
            if (scores.Any(score =>
                    !string.Equals(score.ItemId, sample.ItemId, StringComparison.Ordinal) ||
                    !itemsById.TryGetValue(sample.ItemId, out var corpusItem) ||
                    score.RequiredFactCount != corpusItem.RequiredFacts.Count ||
                    score.BehaviorFactCount != BehaviorFactCount(corpusItem) ||
                    score.SupportedFactCount < 0 ||
                    score.GeneratedFactCount < score.SupportedFactCount ||
                    score.RequiredFactPresentCount < 0 ||
                    score.RequiredFactCount < score.RequiredFactPresentCount ||
                    score.BehaviorFactPresentCount < 0 ||
                    score.BehaviorFactCount < score.BehaviorFactPresentCount ||
                    score.UsefulSupportedFactCount < 0 ||
                    score.UsefulSupportedFactCount > score.SupportedFactCount ||
                    score.TagTruePositiveCount < 0 ||
                    score.TagFalsePositiveCount < 0 ||
                    score.TagFalseNegativeCount < 0 ||
                    score.SafetyFailureCount < 0))
            {
                invalid.Add($"Sample '{sample.SampleId}' contains invalid reviewer counts.");
                continue;
            }

            merged.Add(new SummaryQualificationSampleReview(
                sample.SampleId,
                sample.ItemId,
                scores.Min(score => score.SupportedFactCount),
                scores.Max(score => score.GeneratedFactCount),
                scores.Max(score => score.RequiredFactCount),
                scores.Min(score => score.RequiredFactPresentCount),
                scores.Any(score => score.CriticalHallucination),
                scores.Any(score => score.Contradiction),
                scores.All(score => score.PurposeAccurate),
                scores.Max(score => score.BehaviorFactCount),
                scores.Min(score => score.BehaviorFactPresentCount),
                scores.Min(score => score.UsefulSupportedFactCount),
                scores.All(score => score.OverallFactuallyCorrect),
                scores.All(score => score.ConfidenceAppropriate),
                scores.Min(score => score.TagTruePositiveCount),
                scores.Max(score => score.TagFalsePositiveCount),
                scores.Max(score => score.TagFalseNegativeCount),
                scores.Max(score => score.SafetyFailureCount),
                string.Join("; ", scores.Select(score => score.Limitation).Where(value => !string.IsNullOrWhiteSpace(value)).Distinct(StringComparer.Ordinal))));
        }

        return merged;
    }

    private static int BehaviorFactCount(SummaryQualificationCorpusItem item)
    {
        return item.ImportantInputs.Count +
            item.ImportantOutputs.Count +
            item.SideEffects.Count +
            item.FailureBehavior.Count;
    }

    private static List<string> FailedGates(
        SummaryQualificationGates gates,
        SummaryQualificationMetrics metrics,
        IReadOnlyList<SummaryQualificationSampleReview> reviews,
        SummaryQualificationRetrievalEvidence? retrieval,
        SummaryQualificationDeploymentEvidence? deployment)
    {
        var failed = new List<string>();
        AddMinimum(failed, "First-attempt schema-valid rate", metrics.FirstAttemptSchemaRate, gates.MinimumFirstAttemptSchemaRate);
        AddMinimum(failed, "Eventual completion rate", metrics.EventualCompletionRate, gates.MinimumEventualCompletionRate);
        AddMaximum(failed, "Secret-canary leaks", metrics.SecretCanaryLeaks, gates.MaximumSecretCanaryLeaks);
        AddMaximum(failed, "Critical hallucinations", metrics.CriticalHallucinations, gates.MaximumCriticalHallucinations);
        AddMinimum(failed, "Atomic factual precision", metrics.AtomicFactualPrecision, gates.MinimumAtomicFactualPrecision);
        AddMinimum(failed, "Required-fact recall", metrics.RequiredFactRecall, gates.MinimumRequiredFactRecall);
        foreach (var (stratum, recall) in metrics.RequiredFactRecallByStratum)
        {
            AddMinimum(failed, $"Required-fact recall for stratum '{stratum}'", recall, gates.MinimumStratumRequiredFactRecall);
        }

        AddMaximum(failed, "Reviewer safety failures", reviews.Sum(review => review.SafetyFailureCount), gates.MaximumSafetyFailures);
        if (retrieval is not null)
        {
            AddMaximum(failed, "Retrieval Recall@k regression", retrieval.Baseline.RecallAtK - retrieval.Candidate.RecallAtK, gates.MaximumAbsoluteRetrievalRegression);
            AddMaximum(failed, "Retrieval MRR regression", retrieval.Baseline.MeanReciprocalRank - retrieval.Candidate.MeanReciprocalRank, gates.MaximumAbsoluteRetrievalRegression);
            AddMaximum(failed, "Retrieval nDCG regression", retrieval.Baseline.NdcgAtK - retrieval.Candidate.NdcgAtK, gates.MaximumAbsoluteRetrievalRegression);
            AddMaximum(failed, "Candidate retrieval secret leaks", retrieval.Candidate.SecretLeaks, gates.MaximumSecretCanaryLeaks);
            AddMaximum(failed, "Retrieval safety failures", retrieval.SafetyFailures.Count, gates.MaximumSafetyFailures);
            AddMaximum(failed, "Unresolved material retrieval regressions", retrieval.Assessment.UnresolvedMaterialRegressions, 0);
            if (!retrieval.Baseline.Comparable || !retrieval.Candidate.Comparable || !retrieval.Baseline.Passed || !retrieval.Candidate.Passed)
            {
                failed.Add("No-summary and candidate live-retrieval reports must be comparable and pass their declared suites.");
            }
        }

        if (gates.MaximumP95LatencyMs is { } maximumP95)
        {
            AddMaximum(failed, "P95 latency (ms)", metrics.P95LatencyMs, maximumP95);
        }

        if (gates.MinimumNodesPerMinute is { } minimumRate)
        {
            AddMinimum(failed, "Nodes per minute", metrics.NodesPerMinute, minimumRate);
        }

        if (gates.MaximumTotalTokens is { } maximumTokens)
        {
            if (metrics.TotalTokens is null)
            {
                failed.Add("Provider token usage is required by the deployment budget but was not reported.");
            }
            else
            {
                AddMaximum(failed, "Total tokens", metrics.TotalTokens.Value, maximumTokens);
            }
        }

        if (gates.MaximumTokensPerSuccessfulNode is { } maximumPerNode)
        {
            if (metrics.TokensPerSuccessfulNode is null)
            {
                failed.Add("Per-node token usage is required by the deployment budget but was not reported.");
            }
            else
            {
                AddMaximum(failed, "Tokens per successful node", metrics.TokensPerSuccessfulNode.Value, maximumPerNode);
            }
        }

        if (gates.MaximumTotalDurationMs is { } maximumDuration)
        {
            AddMaximum(failed, "Total measured duration (ms)", metrics.TotalDurationMs, maximumDuration);
        }

        if (gates.MaximumRetryTokenOverheadRatio is { } maximumRetryOverhead)
        {
            AddMaximum(failed, "Retry token overhead ratio", metrics.RetryTokenOverheadRatio, maximumRetryOverhead);
        }

        if (gates.MaximumPeakHostMemoryMb is { } maximumHostMemory)
        {
            if (deployment is null)
            {
                failed.Add("Peak host-memory evidence is required by the deployment budget.");
            }
            else
            {
                AddMaximum(failed, "Peak host memory (MB)", deployment.PeakHostMemoryMb, maximumHostMemory);
            }
        }

        if (gates.MaximumPeakAcceleratorMemoryMb is { } maximumAcceleratorMemory)
        {
            if (deployment?.PeakAcceleratorMemoryMb is not { } peakAcceleratorMemory)
            {
                failed.Add("Peak accelerator-memory evidence is required by the deployment budget.");
            }
            else
            {
                AddMaximum(failed, "Peak accelerator memory (MB)", peakAcceleratorMemory, maximumAcceleratorMemory);
            }
        }

        if (gates.MaximumOnlineCost is { } maximumOnlineCost)
        {
            if (deployment?.ProviderReportedCost is not { } providerCost)
            {
                failed.Add("Provider-reported cost is required by the online deployment budget.");
            }
            else if (providerCost > maximumOnlineCost)
            {
                failed.Add($"Provider-reported cost {providerCost:0.####} exceeds {maximumOnlineCost:0.####}.");
            }
        }

        return failed;
    }

    private static IReadOnlyDictionary<string, double> RequiredRecallByStratum(
        SummaryQualificationSuite suite,
        IReadOnlyList<SummaryQualificationSampleReview> reviews)
    {
        var itemsById = suite.Items.ToDictionary(item => item.Id, StringComparer.Ordinal);
        var result = new Dictionary<string, (int Present, int Required)>(StringComparer.Ordinal);
        foreach (var review in reviews)
        {
            if (!itemsById.TryGetValue(review.ItemId, out var item))
            {
                continue;
            }

            foreach (var stratum in ItemStrata(item))
            {
                var current = result.GetValueOrDefault(stratum);
                result[stratum] = (current.Present + review.RequiredFactPresentCount, current.Required + review.RequiredFactCount);
            }
        }

        return result.ToDictionary(pair => pair.Key, pair => Rate(pair.Value.Present, pair.Value.Required), StringComparer.Ordinal);
    }

    private static IReadOnlyDictionary<string, SummaryQualificationStratumMetrics> MetricsByStratum(
        SummaryQualificationSuite suite,
        IReadOnlyList<SummaryQualificationSampleReview> reviews)
    {
        var itemsById = suite.Items.ToDictionary(item => item.Id, StringComparer.Ordinal);
        var groups = new Dictionary<string, List<SummaryQualificationSampleReview>>(StringComparer.Ordinal);
        foreach (var review in reviews)
        {
            if (!itemsById.TryGetValue(review.ItemId, out var item))
            {
                continue;
            }

            foreach (var stratum in ItemStrata(item))
            {
                if (!groups.TryGetValue(stratum, out var values))
                {
                    values = [];
                    groups[stratum] = values;
                }
                values.Add(review);
            }
        }

        return groups.ToDictionary(
            pair => pair.Key,
            pair =>
            {
                var values = pair.Value;
                return new SummaryQualificationStratumMetrics(
                    values.Count,
                    Rate(values.Sum(value => value.SupportedFactCount), values.Sum(value => value.GeneratedFactCount)),
                    Rate(values.Sum(value => value.RequiredFactPresentCount), values.Sum(value => value.RequiredFactCount)),
                    Rate(values.Count(value => value.PurposeAccurate), values.Count),
                    Rate(values.Sum(value => value.BehaviorFactPresentCount), values.Sum(value => value.BehaviorFactCount)));
            },
            StringComparer.Ordinal);
    }

    private static IEnumerable<string> ItemStrata(SummaryQualificationCorpusItem item)
    {
        return item.Strata
            .Append(item.Language)
            .Append(item.NodeKind.ToString())
            .Append(item.InputSizeBand)
            .Append(item.Criticality)
            .Distinct(StringComparer.Ordinal);
    }

    private static double IdenticalInputStability(
        IReadOnlyList<SummaryQualificationSample> measured,
        int repetitions)
    {
        var groups = measured.GroupBy(sample => sample.ItemId, StringComparer.Ordinal).ToArray();
        if (groups.Length == 0)
        {
            return 0;
        }

        var stable = groups.Count(group =>
            group.Count() == repetitions &&
            group.All(sample => sample.Completed) &&
            group.Select(sample => CodeMeshHash.StableId(
                    sample.Summary,
                    string.Join("\u001e", sample.Tags),
                    sample.Confidence))
                .Distinct(StringComparer.Ordinal)
                .Count() == 1);
        return Rate(stable, groups.Length);
    }

    private static double PerThousand(int facts, long? outputTokens)
    {
        return outputTokens is > 0
            ? (facts * 1000d) / outputTokens.Value
            : 0;
    }

    private static int CountCanaryLeaks(SummaryQualificationSample sample, IReadOnlyList<string> canaries)
    {
        var output = $"{sample.Summary}\n{string.Join("\n", sample.Tags)}";
        return canaries.Count(canary => !string.IsNullOrEmpty(canary) && output.Contains(canary, StringComparison.Ordinal));
    }

    private static double Percentile(IEnumerable<double> values, double percentile)
    {
        var ordered = values.Order().ToArray();
        if (ordered.Length == 0)
        {
            return 0;
        }

        var index = (int)Math.Ceiling(percentile * ordered.Length) - 1;
        return ordered[Math.Clamp(index, 0, ordered.Length - 1)];
    }

    private static double Rate(int numerator, int denominator) => denominator == 0 ? 0 : numerator / (double)denominator;

    private static double HarmonicMean(double left, double right) => left + right == 0 ? 0 : 2 * left * right / (left + right);

    private static void AddMinimum(List<string> failed, string name, double actual, double minimum)
    {
        if (actual < minimum)
        {
            failed.Add($"{name} {actual:0.###} is below {minimum:0.###}.");
        }
    }

    private static void AddMaximum(List<string> failed, string name, double actual, double maximum)
    {
        if (actual > maximum)
        {
            failed.Add($"{name} {actual:0.###} exceeds {maximum:0.###}.");
        }
    }
}

internal static class Fingerprint
{
    public static string Suite(SummaryQualificationSuite suite)
    {
        var parts = new List<string?>
        {
            suite.SchemaVersion,
            suite.Kind,
            suite.Name,
            suite.Version,
            System.Text.Json.JsonSerializer.Serialize(suite.Gates)
        };
        foreach (var item in suite.Items.OrderBy(item => item.Id, StringComparer.Ordinal))
        {
            parts.AddRange([
                item.Id,
                item.RepositoryId,
                item.RepositoryCommit,
                item.NodeId,
                item.ContentHash,
                item.Language,
                item.NodeKind.ToString(),
                item.Name,
                item.Project,
                item.FilePath,
                item.StartLine.ToString(System.Globalization.CultureInfo.InvariantCulture),
                item.EndLine.ToString(System.Globalization.CultureInfo.InvariantCulture),
                item.InputSizeBand,
                item.Criticality,
                string.Join("\u001e", item.Strata.Order(StringComparer.Ordinal)),
                string.Join("\u001e", item.RequiredFacts),
                string.Join("\u001e", item.OptionalFacts),
                string.Join("\u001e", item.ForbiddenClaims),
                string.Join("\u001e", item.RequiredTags),
                string.Join("\u001e", item.AcceptableTags),
                item.Partition,
                item.ExpectedResponsibility,
                string.Join("\u001e", item.ImportantInputs),
                string.Join("\u001e", item.ImportantOutputs),
                string.Join("\u001e", item.SideEffects),
                string.Join("\u001e", item.FailureBehavior),
                item.ReferenceSummary,
                string.Join("\u001e", (item.SecretCanaries ?? []).Order(StringComparer.Ordinal))
            ]);
        }

        return CodeMeshHash.StableId(parts.ToArray());
    }

    public static string Profile(SummaryQualificationProfile profile)
    {
        return CodeMeshHash.StableId(
            profile.SchemaVersion,
            profile.Kind,
            profile.Name,
            profile.IntendedUse,
            profile.EndpointClass,
            profile.Provider,
            profile.Model,
            profile.ModelRevision,
            profile.Quantization,
            profile.NumericPrecision,
            profile.ChatTemplateHash,
            profile.ContextLength.ToString(System.Globalization.CultureInfo.InvariantCulture),
            profile.MaxInputCharacters.ToString(System.Globalization.CultureInfo.InvariantCulture),
            profile.ReasoningTokenReserve.ToString(System.Globalization.CultureInfo.InvariantCulture),
            profile.MaxCompletionTokens.ToString(System.Globalization.CultureInfo.InvariantCulture),
            profile.Repetitions.ToString(System.Globalization.CultureInfo.InvariantCulture),
            Map(profile.GenerationSettings),
            Map(profile.Host),
            Map(profile.OnlinePolicy),
            string.Join("\u001e", (profile.Conditions ?? []).Order(StringComparer.Ordinal)));
    }

    public static string RepositoryIdentity(IReadOnlyList<SummaryQualificationCorpusItem> items)
    {
        return CodeMeshHash.StableId(items
            .Select(item => $"{item.RepositoryId}\u001e{item.RepositoryCommit}")
            .Distinct(StringComparer.Ordinal)
            .Order(StringComparer.Ordinal)
            .ToArray());
    }

    private static string Map(IReadOnlyDictionary<string, string>? values)
    {
        return values is null
            ? string.Empty
            : string.Join("\u001e", values.OrderBy(pair => pair.Key, StringComparer.Ordinal).Select(pair => $"{pair.Key}={pair.Value}"));
    }
}
