using System.Diagnostics;
using Baldur.Warning;

namespace Warning.Tests;

public sealed class AppHostTests
{
    private sealed class FakeView : IWarningView
    {
        public int Shows { get; private set; }
        public int Hides { get; private set; }
        public List<string> Errors { get; } = new();
        public void Show() => Shows++;
        public void Hide() => Hides++;
        public void ShowError(string message) => Errors.Add(message);
    }

    private static string FakePath()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Baldur.sln")))
        {
            directory = directory.Parent;
        }
        Assert.NotNull(directory);
        return Path.Combine(directory.FullName, "infrastructure", "test", "fake_engine.py");
    }

    private static (AppHost Host, FakeView View, MouseBlocker Blocker) StartHost(string arguments)
    {
        var view = new FakeView();
        var blocker = new MouseBlocker(blockingEnabled: false);
        var host = new AppHost(new EngineHost(), view, blocker);
        host.Start("python", $"\"{FakePath()}\" {arguments}");
        return (host, view, blocker);
    }

    [Fact]
    public void BadPostureEngagesViewAndBlock()
    {
        var (host, view, _) = StartHost("--mode script");
        using (host)
        {
            Assert.True(SpinWait.SpinUntil(() => view.Shows > 0, TimeSpan.FromSeconds(30)));
            Assert.True(SpinWait.SpinUntil(() => view.Hides > 0, TimeSpan.FromSeconds(30)));
        }
    }

    [Fact]
    public void WatchdogTripsOnceUntilSignsOfLife()
    {
        var view = new FakeView();
        using var host = new AppHost(new EngineHost(), view, new MouseBlocker(blockingEnabled: false));
        host.Start("python", $"\"{FakePath()}\" --mode infinite");
        Thread.Sleep(1000);
        host.CheckWatchdog(DateTimeOffset.UtcNow.AddSeconds(30));
        Assert.Single(view.Errors);
        Thread.Sleep(1000);
        host.CheckWatchdog(DateTimeOffset.UtcNow.AddSeconds(30));
        Assert.Equal(2, view.Errors.Count);
    }

    [Fact]
    public void DoubleStartThrows()
    {
        var view = new FakeView();
        using var host = new AppHost(new EngineHost(), view, new MouseBlocker(blockingEnabled: false));
        host.Start("python", $"\"{FakePath()}\" --mode infinite");
        Assert.Throws<InvalidOperationException>(() => host.Start("python", "x"));
    }

    [Fact]
    public void SingleRestartThenParksInError()
    {
        var (host, view, _) = StartHost("--mode infinite");
        using (host)
        {
            var firstPid = SpinWait.SpinUntil(() => host.EngineProcessId != 0, TimeSpan.FromSeconds(30));
            Assert.True(firstPid);
            var pidBeforeKill = host.EngineProcessId;
            Process.GetProcessById(pidBeforeKill).Kill();
            Assert.True(SpinWait.SpinUntil(
                () => host.EngineProcessId != 0 && host.EngineProcessId != pidBeforeKill,
                TimeSpan.FromSeconds(30)));
            Process.GetProcessById(host.EngineProcessId).Kill();
            Assert.True(SpinWait.SpinUntil(() => view.Errors.Count > 0, TimeSpan.FromSeconds(30)));
        }
    }

    [Fact]
    public void DisposeReleasesEverythingTwiceSafely()
    {
        var view = new FakeView();
        var host = new AppHost(new EngineHost(), view, new MouseBlocker(blockingEnabled: false));
        host.Start("python", $"\"{FakePath()}\" --mode infinite");
        host.Dispose();
        host.Dispose();
        Assert.Empty(view.Errors);
    }

    [Fact]
    public void FailedStartDoesNotPoisonHost()
    {
        var view = new FakeView();
        using var host = new AppHost(new EngineHost(), view, new MouseBlocker(blockingEnabled: false));
        Assert.ThrowsAny<Exception>(() => host.Start("definitely-not-a-binary-xyz", ""));
        host.Start("python", $"\"{FakePath()}\" --mode infinite");
        Assert.True(SpinWait.SpinUntil(() => host.EngineProcessId != 0, TimeSpan.FromSeconds(30)));
    }

    [Fact]
    public void FaultyViewDoesNotCrashHost()
    {
        var view = new ThrowingView();
        using var host = new AppHost(new EngineHost(), view, new MouseBlocker(blockingEnabled: false));
        host.Start("python", $"\"{FakePath()}\" --mode script");
        Assert.True(SpinWait.SpinUntil(() => view.ErrorCalls > 0, TimeSpan.FromSeconds(30)));
        Assert.True(SpinWait.SpinUntil(() => view.HideCalls > 0, TimeSpan.FromSeconds(30)));
    }

    private sealed class ThrowingView : IWarningView
    {
        public int HideCalls { get; private set; }
        public int ErrorCalls { get; private set; }
        public void Show() => throw new InvalidOperationException("no UI thread");
        public void Hide() => HideCalls++;
        public void ShowError(string message) => ErrorCalls++;
    }
}

public sealed class TrayAndInstanceTests
{
    [StaFact]
    public void TrayConstructsDisposesAndQuitsQuietly()
    {
        using var tray = new Baldur.Warning.TrayController();
        var fired = false;
        tray.QuitRequested += () => fired = true;
        tray.QuitItem.PerformClick();
        Assert.True(fired);
    }

    [Fact]
    public void SecondAcquireFailsUntilReleased()
    {
        var name = "Baldur.Test." + Guid.NewGuid();
        Assert.True(Baldur.Warning.SingleInstance.TryAcquire(name, out var first));
        Assert.False(Baldur.Warning.SingleInstance.TryAcquire(name, out _));
        first.Dispose();
        Assert.True(Baldur.Warning.SingleInstance.TryAcquire(name, out var third));
        third.Dispose();
    }
}
