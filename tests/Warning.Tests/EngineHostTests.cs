using System.Collections.Concurrent;
using System.Diagnostics;
using Baldur.Warning;

namespace Warning.Tests;

/// <summary>W1 (issue #13): host reads the frozen JSON-lines protocol.
/// The fake producer stands in for engine.py until it exists.
/// </summary>
public sealed class EngineHostTests
{
    private static string FakeEnginePath()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Baldur.sln")))
        {
            directory = directory.Parent;
        }
        Assert.NotNull(directory);
        var fake = Path.Combine(directory.FullName, "infrastructure", "test", "fake_engine.py");
        Assert.True(File.Exists(fake), fake);
        return fake;
    }

    private static EngineHost StartHost(string arguments, Action<EngineEvent>? onEvent = null, Action? onExit = null)
    {
        var host = new EngineHost();
        if (onEvent is not null)
        {
            host.EventReceived += onEvent;
        }
        if (onExit is not null)
        {
            host.Exited += onExit;
        }
        host.Start("python", $"\"{FakeEnginePath()}\" {arguments}");
        return host;
    }

    [Fact]
    public void ZeroDropOnCountedStream()
    {
        using var host = StartHost("--mode count --count 10 --interval 0.05");
        var received = new ConcurrentBag<EngineEvent>();
        host.EventReceived += received.Add;
        Assert.True(host.WaitForExit(TimeSpan.FromSeconds(30)));
        Assert.Equal(10, received.Count);
        Assert.All(received, e => Assert.Equal("heartbeat", e.Name));
    }

    [Fact]
    public void ScriptedRunContainsAllFrozenKinds()
    {
        var names = new ConcurrentBag<string>();
        using var host = StartHost("--mode script", e => names.Add(e.Name));
        Assert.True(host.WaitForExit(TimeSpan.FromSeconds(30)));
        Assert.Contains("bad_posture", names);
        Assert.Contains("recovered", names);
        Assert.Contains("heartbeat", names);
    }

    [Fact]
    public void MalformedLineCountedWithoutCrash()
    {
        var good = new ConcurrentBag<EngineEvent>();
        using var host = StartHost("--mode malformed", e => good.Add(e));
        Assert.True(host.WaitForExit(TimeSpan.FromSeconds(30)));
        Assert.Equal(2, good.Count);
        Assert.Equal(1, host.MalformedCount);
    }

    [Fact]
    public void KillMidRunSurfacesExited()
    {
        using var exited = new ManualResetEventSlim();
        using var host = StartHost("--mode infinite", onExit: () => exited.Set());
        Process.GetProcessById(host.ProcessId).Kill();
        Assert.True(exited.Wait(TimeSpan.FromSeconds(30)));
    }

    [Fact]
    public void DisposeLeavesNoOrphanProcess()
    {
        int childId;
        var host = StartHost("--mode infinite");
        childId = host.ProcessId;
        Assert.True(childId > 0);
        host.Dispose();
        Assert.ThrowsAny<Exception>(() => Process.GetProcessById(childId));
    }

    [Fact]
    public void ChattyStderrDoesNotDeadlockReader()
    {
        var received = new ConcurrentBag<EngineEvent>();
        using var host = StartHost("--mode spam", e => received.Add(e));
        Assert.True(host.WaitForExit(TimeSpan.FromSeconds(30)));
        Assert.Equal(5, received.Count);
    }

    [Fact]
    public void StartMissingBinaryThrowsWithoutLeaking()
    {
        using var host = new EngineHost();
        Assert.ThrowsAny<Exception>(() => host.Start("definitely-not-a-binary-xyz", ""));
    }

    [Fact]
    public void StartTwiceThrows()
    {
        using var host = StartHost("--mode infinite");
        Assert.Throws<InvalidOperationException>(() => host.Start("python", "--version"));
    }

    [Fact]
    public void LastReceivedTimestampAdvances()
    {
        using var host = StartHost("--mode infinite");
        var before = host.LastReceivedAtUtc;
        Assert.True(SpinWait.SpinUntil(() => host.LastReceivedAtUtc > before, TimeSpan.FromSeconds(30)));
    }
}
