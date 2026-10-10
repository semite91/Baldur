using System.Windows;
using Baldur.Warning;

namespace Warning.Tests;

public sealed class CameraDialogTests
{
    [StaFact]
    public void StartupDialogShowsMessageAndCloseOnly()
    {
        var dialog = new CameraDialog(withContinue: false);
        try
        {
            Assert.Equal("Camera is unavailable !!!", dialog.MessageText.Text);
            Assert.Equal(Visibility.Collapsed, dialog.ContinueButton.Visibility);
            Assert.Equal(Visibility.Visible, dialog.CloseButton.Visibility);
        }
        finally
        {
            dialog.Close();
        }
    }

    [StaFact]
    public void MidRunDialogShowsBothButtons()
    {
        var dialog = new CameraDialog(withContinue: true);
        try
        {
            Assert.Equal("Camera is unavailable !!!", dialog.MessageText.Text);
            Assert.Equal(Visibility.Visible, dialog.ContinueButton.Visibility);
            Assert.Equal(Visibility.Visible, dialog.CloseButton.Visibility);
        }
        finally
        {
            dialog.Close();
        }
    }

    [StaFact]
    public void CloseButtonRaisesCloseRequested()
    {
        var dialog = new CameraDialog(withContinue: true);
        try
        {
            var fired = false;
            dialog.CloseRequested += () => fired = true;
            dialog.CloseButton.RaiseEvent(new RoutedEventArgs(
                System.Windows.Controls.Primitives.ButtonBase.ClickEvent));
            Assert.True(fired);
        }
        finally
        {
            dialog.Close();
        }
    }

    [StaFact]
    public void ContinueButtonRaisesContinueRequested()
    {
        var dialog = new CameraDialog(withContinue: true);
        try
        {
            var fired = false;
            dialog.ContinueRequested += () => fired = true;
            dialog.ContinueButton.RaiseEvent(new RoutedEventArgs(
                System.Windows.Controls.Primitives.ButtonBase.ClickEvent));
            Assert.True(fired);
        }
        finally
        {
            dialog.Close();
        }
    }

    [StaFact]
    public void ClosingRaisesCloseRequestedOnce()
    {
        var dialog = new CameraDialog(withContinue: false);
        var count = 0;
        dialog.CloseRequested += () => count++;
        dialog.Close();
        Assert.Equal(1, count);
    }
}
