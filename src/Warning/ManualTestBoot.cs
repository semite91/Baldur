using System.IO;
using System.Windows;

namespace Baldur.Warning;

/// <summary>Manual-test entry point (BALDUR_MANUAL_TEST=1): wires the real
/// window, host, blocker and tray against an engine child process.
/// Default is the fake engine; point BALDUR_ENGINE_SCRIPT at the real
/// engine.py (plus BALDUR_ENGINE_PYTHON at the venv python) for true E2E.
/// Never runs in production paths; single-instance explicitly skipped here.</summary>
public static class ManualTestBoot
{
    /// <summary>Resolve which engine child to launch. Pure and unit-tested:
    /// BALDUR_ENGINE_PYTHON (default "python"), BALDUR_ENGINE_SCRIPT
    /// (default fake_engine.py), BALDUR_ENGINE_ARGS (default
    /// BALDUR_MANUAL_FAKE, else "--mode cycle"). The real-engine recipe is
    /// python=B:\venvs\baldur\Scripts\python.exe, script=&lt;root&gt;\engine.py,
    /// args="" (empty: unbounded until Ctrl+C) or "--frames N".</summary>
    public static (string Python, string Arguments) ResolveEngineCommand(
        string repoRoot, Func<string, string?> getenv)
    {
        var python = getenv("BALDUR_ENGINE_PYTHON") ?? "python";
        var script = getenv("BALDUR_ENGINE_SCRIPT")
            ?? Path.Combine(repoRoot, "infrastructure", "test", "fake_engine.py");
        var args = getenv("BALDUR_ENGINE_ARGS")
            ?? getenv("BALDUR_MANUAL_FAKE") ?? "--mode cycle";
        return (python, $"\"{script}\" {args}".TrimEnd());
    }

    public static void Run(System.Windows.Application app)
    {
        var root = FindRepoRoot();
        var configPath = Path.Combine(root, "infrastructure", "test", "manual-config.json");
        var config = WarningConfig.Load(configPath);
        var (enginePython, engineArguments) =
            ResolveEngineCommand(root, Environment.GetEnvironmentVariable);

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
            app.Shutdown();
        }
        tray.QuitRequested += Quit;
        window.QuitRequested += Quit;
        CameraDialog? dialog = null;
        host.CameraDialogRequested += canContinue =>
        {
            if (dialog is not null)
            {
                return;
            }
            dialog = new CameraDialog(canContinue);
            dialog.CloseRequested += Quit;
            dialog.ContinueRequested += () => host.TryResume();
            dialog.Closed += (_, _) => dialog = null;
            dialog.Show();
        };
        host.CameraDialogDismissed += () =>
        {
            var open = dialog;
            dialog = null;
            open?.Hide();
        };
        tray.Show();
        host.Start(enginePython, engineArguments);
        app.Exit += (_, _) =>
        {
            window.ForceClose();
            host.Dispose();
            tray.Dispose();
        };
    }

    private static string FindRepoRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Baldur.sln")))
        {
            directory = directory.Parent;
        }
        if (directory is null)
        {
            throw new InvalidOperationException("Repo root (Baldur.sln) not found above binary dir.");
        }
        return directory.FullName;
    }
}
