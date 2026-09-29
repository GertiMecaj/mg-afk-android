using System.Net.WebSockets;
using System.Text;
using System.Text.Json.Nodes;
using MagicGarden.Windows.Core.State;

namespace MagicGarden.Windows.Core.Protocol;

public sealed record SessionOptions(Uri WebSocketUri,string Cookie,string UserAgent,string Origin);

public sealed class RoomClient : IAsyncDisposable
{
    private readonly CommandSequencer _sequencer=new();
    private ClientWebSocket? _socket;
    private CancellationTokenSource? _lifetime;
    private SessionOptions? _options;
    public AuthoritativeGameState State { get; }=new();
    public GameActions Actions { get; }
    public string PlayerId { get; private set; }="";
    public bool IsAuthoritativeReady => State.Welcomed && !string.IsNullOrWhiteSpace(PlayerId);
    public event Action<JsonObject>? MessageApplied;
    public event Action<string>? ProtocolWarning;

    public RoomClient() => Actions=new GameActions(SendTextAsync,_sequencer);

    public async Task ConnectAsync(SessionOptions options,CancellationToken ct=default)
    {
        await DisconnectAsync();
        _options=options; State.Reset(); _sequencer.Reset(); PlayerId="";
        _lifetime=CancellationTokenSource.CreateLinkedTokenSource(ct);
        _socket=new ClientWebSocket();
        _socket.Options.SetRequestHeader("Cookie",options.Cookie);
        _socket.Options.SetRequestHeader("User-Agent",options.UserAgent);
        _socket.Options.SetRequestHeader("Origin",options.Origin);
        await _socket.ConnectAsync(options.WebSocketUri,_lifetime.Token);
        await SendTextAsync("{\"type\":\"SocketOpened\"}",_lifetime.Token);
        _=ReceiveLoopAsync(_socket,_lifetime.Token);
    }

    private async Task ReceiveLoopAsync(ClientWebSocket ws,CancellationToken ct)
    {
        var buffer=new byte[128*1024];
        try
        {
            while(ws.State==WebSocketState.Open && !ct.IsCancellationRequested)
            {
                using var ms=new MemoryStream();
                WebSocketReceiveResult r;
                do { r=await ws.ReceiveAsync(buffer,ct); if(r.MessageType==WebSocketMessageType.Close) return; ms.Write(buffer,0,r.Count); }
                while(!r.EndOfMessage);
                await HandleIncomingAsync(Encoding.UTF8.GetString(ms.ToArray()),ct);
            }
        }
        catch(OperationCanceledException) when(ct.IsCancellationRequested) {}
        catch(Exception e) { ProtocolWarning?.Invoke("socket receive failed: "+e.Message); }
    }

    public async Task HandleIncomingAsync(string raw,CancellationToken ct=default)
    {
        if(raw is "ping" or "\"ping\"") { await SendTextAsync("pong",ct); return; }
        JsonObject? msg;
        try { msg=JsonNode.Parse(raw) as JsonObject; } catch(Exception e) { ProtocolWarning?.Invoke("incoming parse error: "+e.Message); return; }
        if(msg is null) return;
        if(msg["type"]?.GetValue<string>()=="RoomFrame") msg=AuthoritativeGameState.NormalizeRoomFrame(msg);

        if(msg["type"]?.GetValue<string>()=="Welcome")
        {
            var self=msg["selfPlayerId"]?.GetValue<string>(); if(!string.IsNullOrWhiteSpace(self)) PlayerId=self!;
            if(msg["executedCommandSequence"] is JsonValue seq && seq.TryGetValue<long>(out var executed)) _sequencer.Seed(executed);
            if(!ValidateIdentity(msg)) { ProtocolWarning?.Invoke("Invalid mc_jwt cookie."); await DisconnectAsync(); return; }
            if(!State.Apply(msg)) { ProtocolWarning?.Invoke("Welcome missing fullState."); return; }
            await Actions.VoteForGameAsync(ct);
            await Actions.SetSelectedGameAsync(ct);
            MessageApplied?.Invoke(msg); return;
        }

        if(msg["type"]?.GetValue<string>()=="PartialState")
        {
            if(!State.Welcomed) { ProtocolWarning?.Invoke("Ignoring patch before authoritative Welcome."); return; }
            if(State.Apply(msg)) MessageApplied?.Invoke(msg);
            return;
        }

        if(msg["type"]?.GetValue<string>()=="QuinoaCommandResult" && msg["ok"]?.GetValue<bool>()==false)
            ProtocolWarning?.Invoke($"command rejected type={msg["commandType"]} code={msg["code"]}");
    }

    private bool ValidateIdentity(JsonObject welcome)
    {
        if((welcome["fullState"] as JsonObject)?["data"] is not JsonObject room || room["players"] is not JsonArray players) return true;
        foreach(var n in players)
        {
            if(n is not JsonObject p || p["id"]?.GetValue<string>()!=PlayerId) continue;
            return p["discordUserId"] is not null || p["databaseUserId"] is not null;
        }
        return true;
    }

    private async Task SendTextAsync(string text,CancellationToken ct)
    {
        var ws=_socket ?? throw new InvalidOperationException("Socket is not connected.");
        if(ws.State!=WebSocketState.Open) throw new InvalidOperationException("Socket is not open.");
        var bytes=Encoding.UTF8.GetBytes(text);
        await ws.SendAsync(bytes,WebSocketMessageType.Text,true,ct);
    }

    public async Task DisconnectAsync()
    {
        var cts=_lifetime; _lifetime=null; cts?.Cancel();
        var ws=_socket; _socket=null;
        if(ws is not null)
        {
            try { if(ws.State is WebSocketState.Open or WebSocketState.CloseReceived) await ws.CloseAsync(WebSocketCloseStatus.NormalClosure,"client disconnect",CancellationToken.None); } catch {}
            ws.Dispose();
        }
        cts?.Dispose(); State.Reset(); _sequencer.Reset(); PlayerId="";
    }

    public async ValueTask DisposeAsync()=>await DisconnectAsync();
}
