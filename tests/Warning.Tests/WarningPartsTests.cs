using Baldur.Warning;

namespace Warning.Tests;

public sealed class WarningConfigTests
{
    [Fact]
    public void MissingFileYieldsDefaults()
    {
        var config = WarningConfig.Load(Path.Combine(Path.GetTempPath(), Guid.NewGuid() + ".json"));
        Assert.True(config.IsWarningWindowClosable);
        Assert.True(config.FlashEnabled);
    }

    [Fact]
    public void BothFlagsFalseHonoredExactly()
    {
        var path = Path.GetTempFileName();
        File.WriteAllText(path, """{"IsWarningWindowClosable": false, "FlashEnabled": false}""");
        try
        {
            var config = WarningConfig.Load(path);
            Assert.False(config.IsWarningWindowClosable);
            Assert.False(config.FlashEnabled);
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Fact]
    public void MalformedFileThrowsInsteadOfSilentDefaults()
    {
        var path = Path.GetTempFileName();
        File.WriteAllText(path, "{not json");
        try
        {
            Assert.ThrowsAny<Exception>(() => WarningConfig.Load(path));
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Fact]
    public void LowercaseKeysAccepted()
    {
        var path = Path.GetTempFileName();
        File.WriteAllText(path, """{"iswarningwindowclosable": false, "flashenabled": false}""");
        try
        {
            var config = WarningConfig.Load(path);
            Assert.False(config.IsWarningWindowClosable);
            Assert.False(config.FlashEnabled);
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Fact]
    public void UnknownKeyThrowsInsteadOfSilentIgnore()
    {
        var path = Path.GetTempFileName();
        File.WriteAllText(path, """{"IsWarningWindowClosable": true, "MouseBlocking": true}""");
        try
        {
            Assert.ThrowsAny<Exception>(() => WarningConfig.Load(path));
        }
        finally
        {
            File.Delete(path);
        }
    }
}

public sealed class WarningPolicyTests
{
    [Theory]
    [InlineData(true, false, true)]
    [InlineData(true, true, true)]
    [InlineData(false, false, false)]
    [InlineData(false, true, true)]
    public void CloseMatrix(bool closable, bool dismissed, bool expected)
    {
        Assert.Equal(expected, WarningPolicy.CanClose(closable, dismissed));
    }

    [Theory]
    [InlineData(true, true, true, true)]
    [InlineData(false, true, true, false)]
    [InlineData(true, false, true, false)]
    [InlineData(true, true, false, false)]
    public void FlashMatrix(bool enabled, bool visible, bool rendered, bool expected)
    {
        Assert.Equal(expected, WarningPolicy.ShouldFlash(enabled, visible, rendered));
    }
}

public sealed class WarningControllerTests
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

    private static EngineEvent Named(string name) =>
        new(name, $"{{\"event\": \"{name}\"}}", DateTimeOffset.UtcNow);

    [Fact]
    public void BadPostureShowsExactlyOncePerEpisode()
    {
        var view = new FakeView();
        var controller = new WarningController(view);
        controller.Handle(Named("bad_posture"));
        controller.Handle(Named("bad_posture"));
        Assert.Equal(1, view.Shows);
        Assert.Equal(0, view.Hides);
    }

    [Fact]
    public void RecoveredHides()
    {
        var view = new FakeView();
        var controller = new WarningController(view);
        controller.Handle(Named("bad_posture"));
        controller.Handle(Named("recovered"));
        Assert.Equal(1, view.Shows);
        Assert.Equal(1, view.Hides);
    }

    [Theory]
    [InlineData("heartbeat")]
    [InlineData("error")]
    public void NonPostureEventsLeaveViewUntouched(string name)
    {
        var view = new FakeView();
        var controller = new WarningController(view);
        controller.Handle(Named(name));
        Assert.Equal(0, view.Shows);
        Assert.Equal(0, view.Hides);
    }
}
