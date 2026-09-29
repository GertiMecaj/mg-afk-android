using Xunit;
using System.Text.Json.Nodes;
using MagicGarden.Windows.Core.Protocol;
using MagicGarden.Windows.Core.State;

namespace MagicGarden.Windows.Core.Tests;

public class ProtocolParityTests
{
    [Fact] public void Sequencer_seeds_from_last_executed()
    { var s=new CommandSequencer(); s.Seed(41); Assert.Equal(42,s.Next()); Assert.Equal(43,s.Next()); s.Reset(); Assert.Equal(1,s.Next()); }

    [Fact] public void Pointer_decodes_android_rules()
    { Assert.Equal(new[]{"a/b","c~d"},JsonPatch.DecodePointer("/a~1b/c~0d")); }

    [Fact] public void Welcome_uses_fullstate_data_and_child_data()
    {
        var state=new AuthoritativeGameState();
        var m=JsonNode.Parse("""{"type":"Welcome","fullState":{"data":{"roomId":"r"},"child":{"data":{"weather":"Rain"}}}}""")!.AsObject();
        Assert.True(state.Apply(m)); Assert.True(state.Welcomed);
        Assert.Equal("Rain",state.Weather());
    }

    [Fact] public void RoomFrame_normalizes_to_partial_state()
    {
        var m=JsonNode.Parse("""{"type":"RoomFrame","seq":9,"state":{"patches":[{"op":"replace","path":"/child/data/weather","value":"Sun"}]}}""")!.AsObject();
        var n=AuthoritativeGameState.NormalizeRoomFrame(m);
        Assert.Equal("PartialState",n["type"]!.GetValue<string>());
        Assert.Equal(9,n["seq"]!.GetValue<int>());
        Assert.Single(n["patches"]!.AsArray());
    }

    [Fact] public void Child_patch_routes_to_game_state()
    {
        var state=new AuthoritativeGameState();
        state.Apply(JsonNode.Parse("""{"type":"Welcome","fullState":{"data":{},"child":{"data":{"weather":"Rain"}}}}""")!.AsObject());
        state.Apply(JsonNode.Parse("""{"type":"PartialState","patches":[{"op":"replace","path":"/child/data/weather","value":"Snow"}]}""")!.AsObject());
        Assert.Equal("Snow",state.Weather());
    }

    [Fact] public void User_slot_prefers_server_userId()
    {
        var state=new AuthoritativeGameState();
        state.Apply(JsonNode.Parse("""{"type":"Welcome","fullState":{"data":{},"child":{"data":{"userSlots":[{"userId":"p1","data":{"inventory":{"items":[]}}}]}}}}""")!.AsObject());
        Assert.NotNull(state.ResolveUserSlot("p1"));
    }

    [Fact] public void Keyed_garden_tiles_preserve_tile_id()
    {
        var state=new AuthoritativeGameState();
        var m=new JsonObject { ["type"]="Welcome", ["fullState"]=new JsonObject { ["data"]=new JsonObject(), ["child"]=new JsonObject { ["data"]=new JsonObject { ["userSlots"]=new JsonArray(new JsonObject { ["userId"]="p1", ["data"]=new JsonObject { ["garden"]=new JsonObject { ["tileObjects"]=new JsonObject { ["17"]=new JsonObject { ["objectType"]="plant", ["slots"]=new JsonArray(new JsonObject { ["species"]="Carrot" },new JsonObject { ["species"]="Carrot" }) } } }, ["inventory"]=new JsonObject { ["items"]=new JsonArray() } } }) } } } };
        state.Apply(m);var crops=StateViews.Crops(state,"p1").ToArray();
        Assert.Equal(2,crops.Length);Assert.All(crops,x=>Assert.Equal(17,x.tileObjectIdx));
    }
}
