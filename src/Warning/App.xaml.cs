using System.Configuration;
using System.Data;
using System.Windows;

namespace Warning;

/// <summary>
/// Interaction logic for App.xaml
/// </summary>
public partial class App : System.Windows.Application
{
    protected override void OnStartup(System.Windows.StartupEventArgs e)
    {
        base.OnStartup(e);
        if (System.Environment.GetEnvironmentVariable("BALDUR_MANUAL_TEST") == "1")
        {
            Baldur.Warning.ManualTestBoot.Run(this);
        }
        else
        {
            Baldur.Warning.ProductionBoot.Run(this);
        }
    }
}

