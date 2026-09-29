using System.Text.Json.Nodes;

namespace MagicGarden.Windows.Core.Protocol;

public static class JsonPatch
{
    public static IReadOnlyList<string> DecodePointer(string path) =>
        path.Split('/').Skip(1).Select(x => x.Replace("~1", "/").Replace("~0", "~")).ToArray();

    public static JsonNode? Apply(JsonNode? target, string path, JsonNode? value, string? op)
    {
        var parts = DecodePointer(path).ToList();
        if (parts.Count > 0 && parts[0] == "data") parts.RemoveAt(0);
        if (parts.Count == 0) return value?.DeepClone() ?? target;
        target ??= IsIndex(parts[0]) ? new JsonArray() : new JsonObject();
        ApplyAt(target, parts, 0, value, op);
        return target;
    }

    private static void ApplyAt(JsonNode current, IReadOnlyList<string> parts, int i, JsonNode? value, string? op)
    {
        var key = parts[i];
        var leaf = i == parts.Count - 1;
        if (current is JsonObject obj)
        {
            if (leaf)
            {
                if (op == "remove") obj.Remove(key);
                else obj[key] = value?.DeepClone();
                return;
            }
            var child = obj[key];
            if (child is null)
            {
                child = IsIndex(parts[i + 1]) ? new JsonArray() : new JsonObject();
                obj[key] = child;
            }
            ApplyAt(child, parts, i + 1, value, op);
            return;
        }

        if (current is JsonArray arr && int.TryParse(key, out var index))
        {
            if (leaf)
            {
                if (op == "remove") { if (index >= 0 && index < arr.Count) arr.RemoveAt(index); return; }
                while (arr.Count < index) arr.Add(null);
                if (index < arr.Count) arr[index] = value?.DeepClone();
                else arr.Add(value?.DeepClone());
                return;
            }
            while (arr.Count <= index) arr.Add(null);
            var child = arr[index];
            if (child is null)
            {
                child = IsIndex(parts[i + 1]) ? new JsonArray() : new JsonObject();
                arr[index] = child;
            }
            ApplyAt(child, parts, i + 1, value, op);
        }
    }

    private static bool IsIndex(string s) => int.TryParse(s, out _);
}
