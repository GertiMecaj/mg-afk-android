using System.Text.Json;
using System.Text.Json.Nodes;

namespace MagicGarden.Windows.Core.Protocol;

public sealed class GameActions
{
    private readonly Func<string, CancellationToken, Task> _send;
    private readonly CommandSequencer _sequence;
    private static readonly string[] RoomScope = ["Room"];
    private static readonly string[] GameScope = ["Room", "Quinoa"];
    private static readonly HashSet<string> Raw = new(StringComparer.Ordinal)
    {
        "Ping","PlayerPosition","Teleport","SetSelectedItem","CheckWeatherStatus","CheckFriendBonus",
        "ThrowSnowball","QuinoaTutorialSkipped","RequestPetGreet","DropObject","PickupObject",
        "UpgradePetHutch","UpgradeSeedSilo","UpgradeDecorShed","UpgradeToolShack"
    };

    public GameActions(Func<string,CancellationToken,Task> send, CommandSequencer sequence)
    { _send = send; _sequence = sequence; }

    private Task SendAsync(string[] scope, string type, JsonObject? p, CancellationToken ct)
    {
        var m = new JsonObject { ["scopePath"] = JsonSerializer.SerializeToNode(scope), ["type"] = type };
        if (p is not null) foreach (var kv in p) m[kv.Key] = kv.Value?.DeepClone();
        return _send(m.ToJsonString(), ct);
    }

    public Task RoomAsync(string type, JsonObject? p=null, CancellationToken ct=default) => SendAsync(RoomScope,type,p,ct);

    public Task GameAsync(string type, JsonObject? p=null, CancellationToken ct=default)
    {
        if (Raw.Contains(type)) return SendAsync(GameScope,type,p,ct);
        var command = new JsonObject { ["type"] = type };
        if (p is not null) foreach (var kv in p) command[kv.Key] = kv.Value?.DeepClone();
        var envelope = new JsonObject {
            ["scopePath"] = JsonSerializer.SerializeToNode(GameScope), ["type"] = "QuinoaCommand",
            ["requestId"] = Guid.NewGuid().ToString(), ["commandSequence"] = _sequence.Next(), ["command"] = command
        };
        return _send(envelope.ToJsonString(),ct);
    }

    public Task VoteForGameAsync(CancellationToken ct=default)=>RoomAsync("VoteForGame",new(){["gameName"]="Quinoa"},ct);
    public Task SetSelectedGameAsync(CancellationToken ct=default)=>RoomAsync("SetSelectedGame",new(){["gameName"]="Quinoa"},ct);
    public Task PlantSeedAsync(int slot,string species,CancellationToken ct=default)=>GameAsync("PlantSeed",new(){["slot"]=slot,["species"]=species},ct);
    public Task WaterPlantAsync(int slot,CancellationToken ct=default)=>GameAsync("WaterPlant",new(){["slot"]=slot},ct);
    public Task HarvestCropAsync(int slot,int? slotsIndex=null,CancellationToken ct=default)
    {
        var p=new JsonObject{{"slot",slot},{"cropItemId",Guid.NewGuid().ToString()}};
        if(slotsIndex is not null)p["slotsIndex"]=slotsIndex.Value;
        return GameAsync("HarvestCrop",p,ct);
    }
    public Task SellAllCropsAsync(CancellationToken ct=default)=>GameAsync("SellAllCrops",null,ct);
    public Task GrowEggAsync(int slot,string eggId,CancellationToken ct=default)=>GameAsync("GrowEgg",new(){["slot"]=slot,["eggId"]=eggId},ct);
    public Task HatchEggAsync(int slot,CancellationToken ct=default)=>GameAsync("HatchEgg",new(){["slot"]=slot},ct);
    public Task ApplyPetTeamAsync(string teamId,CancellationToken ct=default)=>GameAsync("ApplyPetTeam",new(){["teamId"]=teamId},ct);
    public Task PutItemInStorageAsync(string itemId,string storageId,CancellationToken ct=default)=>GameAsync("PutItemInStorage",new(){["itemId"]=itemId,["storageId"]=storageId},ct);
    public Task PurchaseShopItemAsync(string shop,string itemType,string idField,string itemId,CancellationToken ct=default)=>
        GameAsync("PurchaseShopItem",new(){["shop"]=shop,["item"]=new JsonObject{{"itemType",itemType},{idField,itemId}}},ct);
}
