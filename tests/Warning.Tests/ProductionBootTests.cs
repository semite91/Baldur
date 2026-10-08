using Baldur.Warning;

namespace Warning.Tests;

public sealed class ProductionBootTests
{
    private static string? Lookup(IReadOnlyDictionary<string, string> env, string name) =>
        env.TryGetValue(name, out var value) ? value : null;

    private static string TempDir()
    {
        var dir = Path.Combine(Path.GetTempPath(), "Baldur.Test." + Guid.NewGuid());
        Directory.CreateDirectory(dir);
        return dir;
    }

    [Fact]
    public void ConfigPathLivesUnderAppData()
    {
        var path = ProductionBoot.ConfigPath();
        Assert.EndsWith(Path.Combine("Baldur", "WarningConfig.json"), path);
        Assert.StartsWith(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), path);
    }

    [Fact]
    public void EnsureConfigSeedsDefaultsOnFirstRun()
    {
        var path = Path.Combine(TempDir(), "sub", "WarningConfig.json");
        var config = ProductionBoot.EnsureConfig(path);
        Assert.Equal(new WarningConfig(), config);
        Assert.True(File.Exists(path));
        Assert.Equal(config, ProductionBoot.EnsureConfig(path));
    }

    [Fact]
    public void EnsureConfigPreservesUserEdits()
    {
        var dir = TempDir();
        var path = Path.Combine(dir, "WarningConfig.json");
        File.WriteAllText(path, """{"IsWarningWindowClosable": false, "FlashEnabled": true}""");
        var config = ProductionBoot.EnsureConfig(path);
        Assert.False(config.IsWarningWindowClosable);
    }

    [Fact]
    public void EnvOverrideWinsOverFrozenBundle()
    {
        var dir = TempDir();
        Directory.CreateDirectory(Path.Combine(dir, "engine"));
        File.WriteAllText(Path.Combine(dir, "engine", "engine.exe"), "x");
        var env = new Dictionary<string, string>
        {
            ["BALDUR_ENGINE_SCRIPT"] = @"C:\dev\engine.py",
        };
        var located = ProductionBoot.LocateEngine(dir, name => Lookup(env, name));
        Assert.NotNull(located);
        Assert.Equal("python", located.Value.File);
        Assert.Equal(@"""C:\dev\engine.py""", located.Value.Args);
    }

    [Fact]
    public void FrozenBundleWithWeightsPassesModelPath()
    {
        var dir = TempDir();
        Directory.CreateDirectory(Path.Combine(dir, "engine", "weights"));
        File.WriteAllText(Path.Combine(dir, "engine", "engine.exe"), "x");
        File.WriteAllText(Path.Combine(dir, "engine", "weights", "yolo26n-pose.pt"), "x");
        var located = ProductionBoot.LocateEngine(
            dir, _ => null);
        Assert.NotNull(located);
        Assert.EndsWith(Path.Combine("engine", "engine.exe"), located.Value.File);
        Assert.Contains("yolo26n-pose.pt", located.Value.Args);
        Assert.StartsWith("--model", located.Value.Args);
    }

    [Fact]
    public void FrozenBundleWithoutWeightsRunsBare()
    {
        var dir = TempDir();
        Directory.CreateDirectory(Path.Combine(dir, "engine"));
        File.WriteAllText(Path.Combine(dir, "engine", "engine.exe"), "x");
        var located = ProductionBoot.LocateEngine(dir, _ => null);
        Assert.NotNull(located);
        Assert.Equal(string.Empty, located.Value.Args);
    }

    [Fact]
    public void FrozenBundleInternalWeightsPassesModelPath()
    {
        var dir = TempDir();
        Directory.CreateDirectory(Path.Combine(dir, "engine", "_internal", "weights"));
        File.WriteAllText(Path.Combine(dir, "engine", "engine.exe"), "x");
        File.WriteAllText(Path.Combine(dir, "engine", "_internal", "weights", "yolo26n-pose.pt"), "x");
        var located = ProductionBoot.LocateEngine(dir, _ => null);
        Assert.NotNull(located);
        Assert.Contains("_internal", located.Value.Args);
        Assert.Contains("yolo26n-pose.pt", located.Value.Args);
    }

    [Fact]
    public void NoEngineReturnsNull()
    {
        Assert.Null(ProductionBoot.LocateEngine(TempDir(), _ => null));
    }
}
