using Baldur.Warning;

namespace Warning.Tests;

/// <summary>W3 (issue #10): hook-plus-clip combo, pure decision seams.
/// Session safety rule: no test ever enables real swallowing; the enabled
/// path differs by one boolean the matrix pins, and is proven manually.</summary>
public sealed class MouseBlockingTests
{
    [Theory]
    [InlineData(Wm.MouseMove, true)]
    [InlineData(Wm.LButtonDown, true)]
    [InlineData(Wm.LButtonUp, true)]
    [InlineData(Wm.RButtonDown, true)]
    [InlineData(Wm.RButtonUp, true)]
    [InlineData(Wm.MButtonDown, true)]
    [InlineData(Wm.MButtonUp, true)]
    [InlineData(Wm.MouseWheel, true)]
    [InlineData(Wm.XButtonDown, true)]
    [InlineData(Wm.XButtonUp, true)]
    public void GatedMessagesSwallowedWhenBlocking(int message, bool _)
    {
        Assert.True(MouseMessageFilter.ShouldSwallow(message, blocking: true));
    }

    [Theory]
    [InlineData(Wm.MouseMove)]
    [InlineData(Wm.LButtonDown)]
    [InlineData(Wm.RButtonDown)]
    [InlineData(Wm.MouseWheel)]
    public void GatedMessagesPassWhenNotBlocking(int message)
    {
        Assert.False(MouseMessageFilter.ShouldSwallow(message, blocking: false));
    }

    [Theory]
    [InlineData(Wm.KeyDown)]
    [InlineData(Wm.KeyUp)]
    [InlineData(Wm.SysKeyDown)]
    public void KeyboardRangeNeverSwallowed(int message)
    {
        Assert.False(MouseMessageFilter.ShouldSwallow(message, blocking: true));
        Assert.False(MouseMessageFilter.ShouldSwallow(message, blocking: false));
    }

    [Fact]
    public void ClipRectIsPrimaryDisplayAtOrigin()
    {
        var rect = MouseBlocker.PrimaryScreenClipRect();
        Assert.Equal(0, rect.X);
        Assert.Equal(0, rect.Y);
        Assert.True(rect.Width > 0);
        Assert.True(rect.Height > 0);
    }

    [Fact]
    public void StartStopLifecycleIsSafe()
    {
        using var blocker = new MouseBlocker(blockingEnabled: false);
        Assert.False(blocker.IsHookInstalled);
        blocker.Start();
        Assert.True(blocker.IsHookInstalled);
        blocker.Stop();
        Assert.False(blocker.IsHookInstalled);
        blocker.Stop();
        Assert.False(blocker.IsHookInstalled);
    }

    [Fact]
    public void DisposeWithoutStartIsSafe()
    {
        using var blocker = new MouseBlocker(blockingEnabled: false);
        blocker.Dispose();
    }
}
