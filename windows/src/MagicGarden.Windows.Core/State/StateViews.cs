using System.Text.Json.Nodes;

namespace MagicGarden.Windows.Core.State;

public static class StateViews
{
    public static IEnumerable<JsonObject> Objects(JsonNode? n) =>
        n is JsonArray a ? a.OfType<JsonObject>() : Enumerable.Empty<JsonObject>();

    public static int InventoryCount(AuthoritativeGameState s,string playerId,string? db=null) => s.InventoryItems(playerId,db).Count;

    public static IEnumerable<(int tileObjectIdx,int growSlotIdx,JsonObject crop)> Crops(AuthoritativeGameState s,string playerId,string? db=null)
    {
        var garden=s.Garden(playerId,db) as JsonObject;
        var tiles=garden?["tileObjects"] as JsonArray;
        if(tiles is null) yield break;
        for(var ti=0;ti<tiles.Count;ti++)
        {
            if(tiles[ti] is not JsonObject tile || tile["slots"] is not JsonArray slots) continue;
            for(var gi=0;gi<slots.Count;gi++) if(slots[gi] is JsonObject crop) yield return(ti,gi,crop);
        }
    }

    public static IEnumerable<JsonObject> OwnedPets(AuthoritativeGameState s,string playerId,string? db=null)
    {
        foreach(var item in Objects(s.InventoryItems(playerId,db)))
            if(item["itemType"]?.GetValue<string>()=="Pet") yield return item;
        foreach(var storage in Objects(s.Storages(playerId,db)))
            if(storage["items"] is JsonArray items)
                foreach(var item in items.OfType<JsonObject>())
                    if(item["itemType"]?.GetValue<string>()=="Pet") yield return item;
    }
}
