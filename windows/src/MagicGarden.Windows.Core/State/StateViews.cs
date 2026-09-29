using System.Text.Json.Nodes;

namespace MagicGarden.Windows.Core.State;

public static class StateViews
{
    public static IEnumerable<JsonObject> Objects(JsonNode? n)=>n is JsonArray a?a.OfType<JsonObject>():Enumerable.Empty<JsonObject>();
    public static int InventoryCount(AuthoritativeGameState s,string playerId,string? db=null)=>s.InventoryItems(playerId,db).Count;

    // Android PlayerModel confirms tileObjects is an object keyed by tile id, not an array.
    // Keep array fallback for older payloads.
    public static IEnumerable<(int tileObjectIdx,int growSlotIdx,JsonObject crop)> Crops(AuthoritativeGameState s,string playerId,string? db=null)
    {
        var garden=s.Garden(playerId,db) as JsonObject;var tiles=garden?["tileObjects"];
        foreach(var (ti,tile) in Tiles(tiles))
        {
            if(tile["slots"] is not JsonArray slots) continue;
            for(var gi=0;gi<slots.Count;gi++) if(slots[gi] is JsonObject crop) yield return(ti,gi,crop);
        }
    }
    public static IEnumerable<(int tileObjectIdx,JsonObject tile)> GardenTiles(AuthoritativeGameState s,string playerId,string? db=null)
    {
        var garden=s.Garden(playerId,db) as JsonObject;
        foreach(var x in Tiles(garden?["tileObjects"]))yield return x;
    }
    private static IEnumerable<(int,JsonObject)> Tiles(JsonNode? n)
    {
        if(n is JsonObject o)foreach(var kv in o)if(kv.Value is JsonObject t&&int.TryParse(kv.Key,out var i))yield return(i,t);
        if(n is JsonArray a)for(var i=0;i<a.Count;i++)if(a[i] is JsonObject t)yield return(i,t);
    }

    // Android getAllPets = inventory + PetHutch + active petSlots.
    public static IEnumerable<JsonObject> OwnedPets(AuthoritativeGameState s,string playerId,string? db=null)
    {
        foreach(var item in Objects(s.InventoryItems(playerId,db)))if(IsPet(item))yield return item;
        foreach(var storage in Objects(s.Storages(playerId,db)))
            if(storage["decorId"]?.GetValue<string>()=="PetHutch"&&storage["items"] is JsonArray items)
                foreach(var item in items.OfType<JsonObject>())if(IsPet(item))yield return item;
        var slot=s.PlayerData(playerId,db);
        if(slot?["petSlots"] is JsonArray active)foreach(var pet in active.OfType<JsonObject>())yield return pet;
    }
    private static bool IsPet(JsonObject x)=>x["itemType"]?.GetValue<string>()=="Pet"||x["petSpecies"] is not null;
}
