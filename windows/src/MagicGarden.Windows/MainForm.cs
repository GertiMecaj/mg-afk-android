using MagicGarden.Windows.Core.Automation;
using MagicGarden.Windows.Core.Protocol;
using MagicGarden.Windows.Core.State;
using System.Text.Json;

namespace MagicGarden.Windows;

public sealed class MainForm : Form
{
    const string DefaultHost="magicgarden.gg";
    const string DefaultUa="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36";
    readonly TextBox host=new(){Text=DefaultHost,PlaceholderText="Host",Dock=DockStyle.Top};
    readonly TextBox version=new(){PlaceholderText="Game version (required)",Dock=DockStyle.Top};
    readonly TextBox room=new(){PlaceholderText="Room ID (required)",Dock=DockStyle.Top};
    readonly TextBox cookie=new(){PlaceholderText="mc_jwt cookie",Dock=DockStyle.Top,UseSystemPasswordChar=true};
    readonly Button connect=new(){Text="CONNECT",Dock=DockStyle.Top,Height=38};
    readonly Label status=new(){Text="DISCONNECTED",Dock=DockStyle.Top,Height=28};
    readonly TabControl tabs=new(){Dock=DockStyle.Fill};
    readonly TextBox log=new(){Dock=DockStyle.Bottom,Multiline=true,ReadOnly=true,Height=150,ScrollBars=ScrollBars.Vertical};
    readonly RoomClient client=new(); CancellationTokenSource? automationCts; AutomationRuntime? runtime; ProjectsPlanner? planner; bool sessionActive;
    readonly CheckedListBox plant=new(){Dock=DockStyle.Fill,CheckOnClick=true};
    readonly CheckedListBox harvest=new(){Dock=DockStyle.Fill,CheckOnClick=true};
    readonly CheckedListBox shop=new(){Dock=DockStyle.Fill,CheckOnClick=true};
    readonly CheckedListBox eggs=new(){Dock=DockStyle.Fill,CheckOnClick=true};
    readonly TextBox feedMap=new(){Dock=DockStyle.Fill,Multiline=true,ScrollBars=ScrollBars.Vertical,PlaceholderText="petItemId=FoodSpecies, one per line"};
    readonly TextBox defaultTeam=new(){Dock=DockStyle.Top,PlaceholderText="Default team ID"};
    readonly TextBox sellTeam=new(){Dock=DockStyle.Top,PlaceholderText="Sell Boost team ID"};
    readonly TextBox hatchTeam=new(){Dock=DockStyle.Top,PlaceholderText="Hatch mutation team ID"};
    readonly TextBox weatherTeams=new(){Dock=DockStyle.Fill,Multiline=true,PlaceholderText="weather=teamId, one per line"};
    readonly NumericUpDown capacity=new(){Dock=DockStyle.Top,Minimum=0,Maximum=100000,Value=100};
    readonly CheckBox dryRun=new(){Text="DRY RUN / SIMULATION MODE",Dock=DockStyle.Top,Checked=true,Height=30};
    readonly Label diag=new(){Dock=DockStyle.Fill,AutoSize=false,Font=new Font(FontFamily.GenericMonospace,10),Padding=new Padding(10)};

    public MainForm(){
        Text="Magic Garden";Width=1100;Height=780;StartPosition=FormStartPosition.CenterScreen;
        Controls.Add(tabs);Controls.Add(log);Controls.Add(status);Controls.Add(connect);Controls.Add(cookie);Controls.Add(room);Controls.Add(version);Controls.Add(host);
        tabs.TabPages.Add(ListPage("A — Auto Plant",plant,"Enabled seed species"));
        tabs.TabPages.Add(ListPage("B — Harvest / Sell",harvest,"Enabled crop species to harvest",capacity,sellTeam));
        tabs.TabPages.Add(ListPage("C — Auto Shop",shop,"Enabled shop item IDs"));
        tabs.TabPages.Add(TextPage("D — Emergency Feed",feedMap,"petItemId=FoodSpecies. Triggers at ≤10% hunger."));
        tabs.TabPages.Add(ListPage("E — Eggs",eggs,"Enabled egg IDs",hatchTeam));
        tabs.TabPages.Add(TextPage("F — Pet Teams",weatherTeams,"weather=teamId",defaultTeam));
        var d=new TabPage("Diagnostics");d.Controls.Add(diag);d.Controls.Add(dryRun);tabs.TabPages.Add(d);
        connect.Click+=async(_,__)=>await Toggle();
        foreach(var b in new[]{plant,harvest,shop,eggs}) b.ItemCheck+=(_,__)=>BeginInvoke(()=>ConfigChanged());
        foreach(var t in new[]{feedMap,defaultTeam,sellTeam,hatchTeam,weatherTeams}) t.TextChanged+=(_,__)=>ConfigChanged();
        capacity.ValueChanged+=(_,__)=>ConfigChanged();dryRun.CheckedChanged+=(_,__)=>ConfigChanged();
        LoadSettings();
        client.ProtocolWarning+=x=>Ui(()=>Append("WARN "+x));
        client.Disconnected+=()=>Ui(OnSocketDisconnected);
        client.MessageApplied+=_=>Ui(OnState);
    }
    static TabPage ListPage(string title,CheckedListBox list,string help,params Control[] top){
        var p=new TabPage(title);p.Controls.Add(list);foreach(var x in top.Reverse())p.Controls.Add(x);p.Controls.Add(new Label{Text=help,Dock=DockStyle.Top,Height=28});return p;
    }
    static TabPage TextPage(string title,Control body,string help,params Control[] top){
        var p=new TabPage(title);p.Controls.Add(body);foreach(var x in top.Reverse())p.Controls.Add(x);p.Controls.Add(new Label{Text=help,Dock=DockStyle.Top,Height=28});return p;
    }
    async Task Toggle(){
        if(sessionActive){connect.Enabled=false;try{automationCts?.Cancel();automationCts?.Dispose();automationCts=null;runtime=null;planner=null;await client.DisconnectAsync();Append("Disconnected.");}finally{sessionActive=false;status.Text="DISCONNECTED";connect.Text="CONNECT";connect.Enabled=true;}return;}
        var h=host.Text.Trim();var v=version.Text.Trim();var roomId=room.Text.Trim();var rawCookie=cookie.Text.Trim();
        if(string.IsNullOrWhiteSpace(h)||string.IsNullOrWhiteSpace(v)||string.IsNullOrWhiteSpace(roomId)||string.IsNullOrWhiteSpace(rawCookie)){Append("Host, game version, room ID and mc_jwt cookie are required.");return;}
        var uri=BuildSocketUri(h,v,roomId,Guid.NewGuid().ToString(),1,"navigate");
        var normalized=rawCookie.Contains("mc_jwt",StringComparison.OrdinalIgnoreCase)?rawCookie:"mc_jwt="+rawCookie;
        status.Text="CONNECTING";connect.Text="DISCONNECT";connect.Enabled=false;sessionActive=true;
        try{await client.ConnectAsync(new SessionOptions(uri,normalized,DefaultUa,"https://"+h));runtime=new AutomationRuntime(client);runtime.Controller.Log+=Append;planner=new ProjectsPlanner(client,runtime.Confirmation);runtime.Configure(planner,Settings,()=>dryRun.Checked);automationCts=new();_=runtime.Controller.RunAsync(automationCts.Token);status.Text="SYNCING — WAITING FOR WELCOME";Append("Socket opened; SocketOpened sent; waiting for authoritative Welcome.");}
        catch(Exception e){Append("CONNECT FAILED "+e.Message);await client.DisconnectAsync();sessionActive=false;status.Text="DISCONNECTED";connect.Text="CONNECT";}
        finally{connect.Enabled=true;}
    }
    void OnSocketDisconnected(){
        runtime?.Controller.ReplaceIntents([]);if(runtime is not null)runtime.Controller.AuthoritativeReady=false;
        status.Text="DISCONNECTED — RECONNECT REQUIRED";Append("Connection lost. Automation paused; no stale state will be used.");
    }
    void OnState(){
        status.Text=client.IsAuthoritativeReady?"CONNECTED — AUTHORITATIVE STATE":"SYNCING";
        PopulateFromState();
        if(runtime is not null&&planner is not null){
            var cfg=Settings();
            var intents=planner.Build(cfg).ToArray();
            runtime.Replan();
            diag.Text=$"Connection: {status.Text}\r\nPlayer: {client.PlayerId}\r\nState revision: {client.State.Revision}\r\nWeather: {client.State.Weather()}\r\nInventory: {client.State.InventoryItems(client.PlayerId).Count}/{capacity.Value}\r\nQueued decisions: {intents.Length}\r\nDry run: {dryRun.Checked}";
        }
    }
    void ConfigChanged(){runtime?.Replan();SaveSettings();}
    sealed record UiSettings(string Host,string Version,string Room,string[] Plant,string[] Harvest,string[] Shop,string[] Eggs,string Feed,string DefaultTeam,string? SellTeam,string? HatchTeam,string Weather,int Capacity,bool DryRun);
    string SettingsPath=>Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"MagicGarden","settings.json");
    void SaveSettings(){try{Directory.CreateDirectory(Path.GetDirectoryName(SettingsPath)!);var x=new UiSettings(host.Text,version.Text,room.Text,Checked(plant).ToArray(),Checked(harvest).ToArray(),Checked(shop).ToArray(),Checked(eggs).ToArray(),feedMap.Text,defaultTeam.Text,Null(sellTeam.Text),Null(hatchTeam.Text),weatherTeams.Text,(int)capacity.Value,dryRun.Checked);File.WriteAllText(SettingsPath,JsonSerializer.Serialize(x));}catch{}}
    void LoadSettings(){try{if(!File.Exists(SettingsPath))return;var x=JsonSerializer.Deserialize<UiSettings>(File.ReadAllText(SettingsPath));if(x is null)return;host.Text=x.Host;version.Text=x.Version;room.Text=x.Room;feedMap.Text=x.Feed;defaultTeam.Text=x.DefaultTeam;sellTeam.Text=x.SellTeam??"";hatchTeam.Text=x.HatchTeam??"";weatherTeams.Text=x.Weather;capacity.Value=Math.Clamp(x.Capacity,(int)capacity.Minimum,(int)capacity.Maximum);dryRun.Checked=x.DryRun;RestoreChecks(plant,x.Plant);RestoreChecks(harvest,x.Harvest);RestoreChecks(shop,x.Shop);RestoreChecks(eggs,x.Eggs);}catch{}}
    static void RestoreChecks(CheckedListBox b,IEnumerable<string> values){foreach(var v in values){var i=b.Items.IndexOf(v);if(i<0)i=b.Items.Add(v);b.SetItemChecked(i,true);}}
    ProjectSettings Settings()=>new(client.PlayerId,null,Checked(plant),Checked(harvest),Checked(shop),Checked(eggs),Pairs(feedMap.Text),Pairs(weatherTeams.Text),defaultTeam.Text.Trim(),Null(sellTeam.Text),Null(hatchTeam.Text),(int)capacity.Value);
    static IReadOnlySet<string> Checked(CheckedListBox b)=>b.CheckedItems.Cast<object>().Select(x=>x.ToString()!).ToHashSet(StringComparer.Ordinal);
    static IReadOnlyDictionary<string,string> Pairs(string text)=>text.Split('\n',StringSplitOptions.RemoveEmptyEntries).Select(x=>x.Trim()).Where(x=>x.Contains('=')).Select(x=>x.Split('=',2)).Where(x=>x.Length==2).ToDictionary(x=>x[0].Trim(),x=>x[1].Trim(),StringComparer.Ordinal);
    static string? Null(string s)=>string.IsNullOrWhiteSpace(s)?null:s.Trim();
    void PopulateFromState(){
        AddDistinct(plant,StateViews.Crops(client.State,client.PlayerId).Select(x=>Str(x.crop,"species")));
        AddDistinct(harvest,StateViews.Crops(client.State,client.PlayerId).Select(x=>Str(x.crop,"species")));
        var shops=client.State.Shops().ToJsonString();
        // IDs remain manually addable; state-discovered identifiers are offered when recognizable.
        try{var root=System.Text.Json.Nodes.JsonNode.Parse(shops);var ids=Desc(root).SelectMany(o=>new[]{"species","toolId","eggId","decorId"}.Select(k=>Str(o,k)));AddDistinct(shop,ids);AddDistinct(eggs,Desc(root).Select(o=>Str(o,"eggId")));}catch{}
    }
    static IEnumerable<System.Text.Json.Nodes.JsonObject> Desc(System.Text.Json.Nodes.JsonNode? n){if(n is System.Text.Json.Nodes.JsonObject o){yield return o;foreach(var v in o)foreach(var z in Desc(v.Value))yield return z;}else if(n is System.Text.Json.Nodes.JsonArray a)foreach(var v in a)foreach(var z in Desc(v))yield return z;}
    static string? Str(System.Text.Json.Nodes.JsonObject? o,string k)=>o?[k] is System.Text.Json.Nodes.JsonValue v&&v.TryGetValue<string>(out var x)?x:null;
    static void AddDistinct(CheckedListBox b,IEnumerable<string?> vals){var have=b.Items.Cast<object>().Select(x=>x.ToString()).ToHashSet();foreach(var x in vals.Where(x=>!string.IsNullOrWhiteSpace(x)).Distinct())if(have.Add(x))b.Items.Add(x);}
    static Uri BuildSocketUri(string h,string v,string r,string d,int a,string nav){var q=new[]{Pair("surface","\"web\""),Pair("platform","\"desktop\""),Pair("version","\""+v+"\""),Pair("capabilities","\"fbo_mipmap_unsupported\""),Pair("locale","\"en\""),Pair("clientDocumentId","\""+d+"\""),Pair("clientConnectionAttempt",a.ToString()),Pair("clientNavigationType","\""+nav+"\""),Pair("clientVisibilityState","\"visible\"")};return new Uri($"wss://{h}/version/{Uri.EscapeDataString(v)}/api/rooms/{Uri.EscapeDataString(r)}/connect?{string.Join("&",q)}");}
    static string Pair(string k,string v)=>Uri.EscapeDataString(k)+"="+Uri.EscapeDataString(v);
    void Append(string s){if(InvokeRequired){BeginInvoke(()=>Append(s));return;}log.AppendText($"[{DateTime.Now:T}] {s}{Environment.NewLine}");}
    void Ui(Action a){if(InvokeRequired)BeginInvoke(a);else a();}
    protected override async void OnFormClosed(FormClosedEventArgs e){SaveSettings();automationCts?.Cancel();await client.DisposeAsync();base.OnFormClosed(e);}
}
