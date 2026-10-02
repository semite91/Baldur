using System.Text.Json;

namespace Baldur.Warning;

/// <summary>One frozen JSON line from the engine: bad_posture, recovered, heartbeat or error.</summary>
public sealed record EngineEvent(string Name, string RawLine, DateTimeOffset ReceivedAt)
{
    private static readonly HashSet<string> FrozenNames = new(StringComparer.Ordinal)
    {
        "bad_posture", "recovered", "heartbeat", "error",
    };

    public static bool TryParse(string? line, out EngineEvent? parsed)
    {
        parsed = null;
        if (string.IsNullOrWhiteSpace(line))
        {
            return false;
        }
        try
        {
            using var document = JsonDocument.Parse(line);
            if (!document.RootElement.TryGetProperty("event", out var name) ||
                name.ValueKind != JsonValueKind.String)
            {
                return false;
            }
            var eventName = name.GetString()!;
            if (!FrozenNames.Contains(eventName))
            {
                return false;
            }
            parsed = new EngineEvent(eventName, line, DateTimeOffset.UtcNow);
            return true;
        }
        catch (JsonException)
        {
            return false;
        }
    }
}
