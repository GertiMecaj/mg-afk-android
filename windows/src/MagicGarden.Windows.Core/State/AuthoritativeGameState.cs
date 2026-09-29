using System.Text.Json.Nodes;
using MagicGarden.Windows.Core.Protocol;

namespace MagicGarden.Windows.Core.State;

public sealed class AuthoritativeGameState
{
    public JsonNode? RoomState { get; private set; }
    public JsonNode? GameState { get; private set; }
    public bool Welcomed { get; private set; }
    public long Revision { get; private set; }

    public void Reset() { RoomState=null; GameState=null; Welcomed=false; Revision++; }

    public bool Apply(JsonObject message)
    {
        var type=message["type"]?.GetValue<string>();
        if(type=="Welcome") return ApplyWelcome(message);
        if(type=="RoomFrame") message=NormalizeRoomFrame(message);
        if(message["type"]?.GetValue<string>()=="PartialState") return ApplyPatches(message);
        return false;
    }

    private bool ApplyWelcome(JsonObject message)
    {
        var full=message["fullState"] as JsonObject;
        if(full is null) return false;
        RoomState=full["data"]?.DeepClone();
        GameState=(full["child"] as JsonObject)?["data"]?.DeepClone();
        Welcomed=true; Revision++; return true;
    }

    private bool ApplyPatches(JsonObject message)
    {
        if(message["patches"] is not JsonArray patches || patches.Count==0) return false;
        var changed=false;
        foreach(var node in patches)
        {
            if(node is not JsonObject p) continue;
            var path=p["path"]?.GetValue<string>(); if(string.IsNullOrEmpty(path)) continue;
            var op=p["op"]?.GetValue<string>(); var value=p["value"];
            if(IsRoomPatch(path!) && RoomState is not null) { RoomState=JsonPatch.Apply(RoomState,path!,value,op); changed=true; }
            else if(path!.StartsWith("/child",StringComparison.Ordinal) && GameState is not null)
            { GameState=JsonPatch.Apply(GameState,path[6..],value,op); changed=true; }
        }
        if(changed) Revision++; return changed;
    }

    public JsonObject? ResolveUserSlot(string playerId, string? databaseId=null)
    {
        if(GameState is not JsonObject game || game["userSlots"] is not JsonArray slots) return null;
        foreach(var n in slots) if(n is JsonObject s && MatchesPlayer(s,playerId)) return s;
        if(!string.IsNullOrWhiteSpace(databaseId))
            foreach(var n in slots) if(n is JsonObject s && MatchesDatabase(s,databaseId!)) return s;
        return null;
    }

    public JsonObject? PlayerData(string playerId,string? databaseId=null)=>ResolveUserSlot(playerId,databaseId)?["data"] as JsonObject;
    public JsonArray InventoryItems(string playerId,string? databaseId=null)=>(PlayerData(playerId,databaseId)?["inventory"] as JsonObject)?["items"] as JsonArray ?? new();
    public JsonArray Storages(string playerId,string? databaseId=null)=>(PlayerData(playerId,databaseId)?["inventory"] as JsonObject)?["storages"] as JsonArray ?? new();
    public JsonNode? Garden(string playerId,string? databaseId=null)=>PlayerData(playerId,databaseId)?["garden"];
    public JsonObject Shops()=> (GameState as JsonObject)?["shops"] as JsonObject ?? new();
    public string? Weather()=> (GameState as JsonObject)?["weather"]?.GetValue<string>();

    public static JsonObject NormalizeRoomFrame(JsonObject msg)
    {
        if(msg["type"]?.GetValue<string>()!="RoomFrame" || (msg["state"] as JsonObject)?["patches"] is not JsonNode patches) return msg;
        var n=new JsonObject();
        foreach(var kv in msg) if(kv.Key is not ("type" or "state")) n[kv.Key]=kv.Value?.DeepClone();
        n["type"]="PartialState"; n["patches"]=patches.DeepClone(); return n;
    }

    private static bool IsRoomPatch(string p) =>
        System.Text.RegularExpressions.Regex.IsMatch(p,@"^/data/players/\d+(/.*)?$") ||
        System.Text.RegularExpressions.Regex.IsMatch(p,@"^/data/(roomId|roomSessionId|hostPlayerId|gameVotes|chat|selectedGame)(/.*)?$");

    private static bool MatchesPlayer(JsonObject s,string id)
    {
        if(string.IsNullOrEmpty(id)) return false;
        if(Str(s,"userId")==id || Str(s,"playerId")==id) return true;
        return s["data"] is JsonObject d && Str(d,"playerId")==id;
    }
    private static bool MatchesDatabase(JsonObject s,string id)
    {
        if(Str(s,"discordUserId")==id || Str(s,"databaseUserId")==id) return true;
        return s["data"] is JsonObject d && (Str(d,"discordUserId")==id || Str(d,"databaseUserId")==id || Str(d,"userId")==id);
    }
    private static string? Str(JsonObject o,string k)=>o[k] is JsonValue v && v.TryGetValue<string>(out var s)?s:null;
}
