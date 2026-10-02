using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Baldur.Warning;

/// <summary>Warning-stage configuration. Missing file means defaults.</summary>
[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record WarningConfig(bool IsWarningWindowClosable = true, bool FlashEnabled = true)
{
    public static WarningConfig Load(string path)
    {
        if (!File.Exists(path))
        {
            return new WarningConfig();
        }
        using var stream = File.OpenRead(path);
        var loaded = JsonSerializer.Deserialize<WarningConfig>(stream, new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true,
        });
        return loaded ?? new WarningConfig();
    }
}
