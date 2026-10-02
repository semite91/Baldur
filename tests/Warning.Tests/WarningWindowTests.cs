using System.Windows;
using Baldur.Warning;

namespace Warning.Tests;

public sealed class WarningWindowTests
{
    [StaFact]
    public void WindowLoadsWithExpectedChrome()
    {
        var window = new WarningWindow();
        try
        {
            Assert.Equal(WindowState.Maximized, window.WindowState);
            Assert.True(window.Topmost);
            Assert.Equal("STAND TALL!!!", window.HeaderText.Text);
            Assert.Contains("ESC", window.EscHint.Text);
            Assert.NotNull(window.PostureImage.Source);
        }
        finally
        {
            window.Close();
        }
    }

    [StaFact]
    public void UnclosableWindowBlocksUserClose()
    {
        var window = new WarningWindow(new WarningConfig(IsWarningWindowClosable: false));
        try
        {
            var closed = false;
            window.Closed += (_, _) => closed = true;
            window.Close();
            Assert.False(closed);
        }
        finally
        {
            window.DismissForRecovery();
        }
    }

    [StaFact]
    public void ForceCloseBypassesUserClosePolicy()
    {
        var window = new WarningWindow(new WarningConfig(IsWarningWindowClosable: false));
        var closed = false;
        window.Closed += (_, _) => closed = true;
        window.ForceClose();
        Assert.True(closed);
    }
}
