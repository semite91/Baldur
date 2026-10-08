using System.IO;
using System.Text.Json;

namespace Baldur.Warning;

/// <summary>Release boot path (no dev flags): single instance, per-user
/// config seeded with defaults, side-by-side frozen engine, tray presence.
/// BALDUR_ENGINE_* env vars still override the engine launch so this path
/// is testable on dev machines without a frozen bundle.</summary>
public static class ProductionBoot
{
    public const string MutexName = "Baldur.Warning";

    private static IDisposable? _lease;

    public static void Run(System.Windows.Application app)
    {
        if (!SingleInstance.TryAcquire(MutexName, out var lease))
        {
            app.Shutdown();
            return;
        }
        _lease = lease;
        var config = EnsureConfig(ConfigPath());
        var engine = LocateEngine(AppContext.BaseDirectory, Environment.GetEnvironmentVariable);
        if (engine is null)
        {
            Console.Error.WriteLine(
                "baldur[boot] engine not found (no side-by-side engine.exe and no BALDUR_ENGINE_SCRIPT override)");
            _lease?.Dispose();
            _lease = null;
            app.Shutdown(1);
            return;
        }

        var window = new WarningWindow(config);
        var host = new AppHost(new EngineHost(), window, new MouseBlocker(config.IsMouseEventsEnabled));
        var tray = new TrayController();
        var quitStarted = false;
        void Quit()
        {
            if (quitStarted)
            {
                return;
            }
            quitStarted = true;
            window.ForceClose();
            host.Dispose();
            tray.Dispose();
            _lease?.Dispose();
            _lease = null;
            app.Shutdown();
        }
        tray.QuitRequested += Quit;
        window.QuitRequested += Quit;
        tray.Show();
        host.Start(engine.Value.File, engine.Value.Args);
        app.Exit += (_, _) =>
        {
            window.ForceClose();
            host.Dispose();
            tray.Dispose();
            _lease?.Dispose();
            _lease = null;
        };
    }

    public static string ConfigPath() => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        "Baldur", "WarningConfig.json");

    /// <summary>Load the per-user config, seeding it with defaults on first
    /// run so users can edit it without admin rights.</summary>
    public static WarningConfig EnsureConfig(string path)
    {
        var directory = Path.GetDirectoryName(path);
        if (directory is not null)
        {
            Directory.CreateDirectory(directory);
        }
        if (!File.Exists(path))
        {
            using var stream = File.Create(path);
            JsonSerializer.Serialize(stream, new WarningConfig());
        }
        return WarningConfig.Load(path);
    }

    /// <summary>Resolve which engine to launch: explicit env override wins
    /// (dev), else the side-by-side frozen bundle with bundled weights when
    /// present. Null when neither exists.</summary>
    public static (string File, string Args)? LocateEngine(
        string baseDir, Func<string, string?> getenv)
    {
        var script = getenv("BALDUR_ENGINE_SCRIPT");
        if (script is not null)
        {
            var args = getenv("BALDUR_ENGINE_ARGS") ?? string.Empty;
            var python = getenv("BALDUR_ENGINE_PYTHON") ?? "python";
            return (python, $"\"{script}\" {args}".TrimEnd());
        }
        var frozen = Path.Combine(baseDir, "engine", "engine.exe");
        if (!File.Exists(frozen))
        {
            return null;
        }
        // PyInstaller v6+ stages data under _internal; a hand-placed copy
        // directly under engine\ is also honored.
        foreach (var weightsDir in new[] { "weights", "_internal/weights" })
        {
            var weights = Path.Combine(baseDir, "engine", weightsDir, "yolo26n-pose.pt");
            if (File.Exists(weights))
            {
                return (frozen, $"--model \"{weights}\"");
            }
        }
        return (frozen, string.Empty);
    }
}
