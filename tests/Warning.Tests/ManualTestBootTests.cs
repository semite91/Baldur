using Baldur.Warning;

namespace Warning.Tests;

public sealed class ManualTestBootTests
{
    private static string? Lookup(IReadOnlyDictionary<string, string> env, string name) =>
        env.TryGetValue(name, out var value) ? value : null;

    [Fact]
    public void DefaultsToFakeCycle()
    {
        var (python, arguments) = ManualTestBoot.ResolveEngineCommand(
            @"C:\repo", name => null);
        Assert.Equal("python", python);
        Assert.Equal(@"""C:\repo\infrastructure\test\fake_engine.py"" --mode cycle", arguments);
    }

    [Fact]
    public void ManualFakeVarStillHonored()
    {
        var env = new Dictionary<string, string> { ["BALDUR_MANUAL_FAKE"] = "--mode die-after --count 5" };
        var (_, arguments) = ManualTestBoot.ResolveEngineCommand(
            @"C:\repo", name => Lookup(env, name));
        Assert.EndsWith("--mode die-after --count 5", arguments);
    }

    [Fact]
    public void EngineArgsBeatManualFake()
    {
        var env = new Dictionary<string, string>
        {
            ["BALDUR_MANUAL_FAKE"] = "--mode cycle",
            ["BALDUR_ENGINE_ARGS"] = "--frames 30",
        };
        var (_, arguments) = ManualTestBoot.ResolveEngineCommand(
            @"C:\repo", name => Lookup(env, name));
        Assert.EndsWith("--frames 30", arguments);
    }

    [Fact]
    public void RealEngineRecipeResolves()
    {
        var env = new Dictionary<string, string>
        {
            ["BALDUR_ENGINE_PYTHON"] = @"B:\venvs\baldur\Scripts\python.exe",
            ["BALDUR_ENGINE_SCRIPT"] = @"C:\repo\engine.py",
            ["BALDUR_ENGINE_ARGS"] = "",
        };
        var (python, arguments) = ManualTestBoot.ResolveEngineCommand(
            @"C:\repo", name => Lookup(env, name));
        Assert.Equal(@"B:\venvs\baldur\Scripts\python.exe", python);
        Assert.Equal(@"""C:\repo\engine.py""", arguments);
    }
}
