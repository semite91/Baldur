using Xunit;

// System-level side effects (global mouse hooks, child processes, windows)
// must never run concurrently: parallel collections deadlocked the suite.
[assembly: CollectionBehavior(DisableTestParallelization = true)]
