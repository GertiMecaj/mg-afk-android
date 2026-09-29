using MagicGarden.Windows.Core.Automation;
using MagicGarden.Windows.Core.Protocol;

namespace MagicGarden.Windows;

public sealed class MainForm : Form
{
    const string DefaultHost = "magicgarden.gg";
    const string DefaultVersion = "db34dc9";
    const string DefaultUa = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36";

    readonly TextBox host = new() { Text = DefaultHost, PlaceholderText = "Host", Dock = DockStyle.Top };
    readonly TextBox version = new() { Text = DefaultVersion, PlaceholderText = "Game version", Dock = DockStyle.Top };
    readonly TextBox room = new() { PlaceholderText = "Room ID (leave blank to generate)", Dock = DockStyle.Top };
    readonly TextBox cookie = new() { PlaceholderText = "mc_jwt cookie", Dock = DockStyle.Top, UseSystemPasswordChar = true };
    readonly Button connect = new() { Text = "CONNECT", Dock = DockStyle.Top, Height = 38 };
    readonly Label status = new() { Text = "DISCONNECTED", Dock = DockStyle.Top, Height = 28 };
    readonly TabControl tabs = new() { Dock = DockStyle.Fill };
    readonly TextBox log = new() { Dock = DockStyle.Bottom, Multiline = true, ReadOnly = true, Height = 150, ScrollBars = ScrollBars.Vertical };

    readonly RoomClient client = new();
    CancellationTokenSource? automationCts;
    AutomationRuntime? runtime;
    bool sessionActive;
    string documentId = "";

    public MainForm()
    {
        Text = "Magic Garden"; Width = 1000; Height = 720; StartPosition = FormStartPosition.CenterScreen;
        Controls.Add(tabs); Controls.Add(log); Controls.Add(status); Controls.Add(connect);
        Controls.Add(cookie); Controls.Add(room); Controls.Add(version); Controls.Add(host);
        foreach (var x in new[] { "A — Auto Plant", "B — Harvest / Sell", "C — Auto Shop", "D — Emergency Feed", "E — Eggs", "F — Pet Teams" })
            tabs.TabPages.Add(MakePage(x));

        connect.Click += async (_, __) => await Toggle();
        client.ProtocolWarning += x => Ui(() => Append("WARN " + x));
        client.MessageApplied += _ => Ui(() =>
        {
            status.Text = client.IsAuthoritativeReady ? "CONNECTED — AUTHORITATIVE STATE" : "SYNCING";
        });
    }

    TabPage MakePage(string title)
    {
        var p = new TabPage(title);
        p.Controls.Add(new Label { Text = title + " configuration", Dock = DockStyle.Top, Height = 35 });
        return p;
    }

    async Task Toggle()
    {
        // Disconnect must work at every stage: connecting, socket-open, syncing or welcomed.
        if (sessionActive)
        {
            connect.Enabled = false;
            try
            {
                automationCts?.Cancel();
                automationCts?.Dispose();
                automationCts = null;
                runtime = null;
                await client.DisconnectAsync();
                Append("Disconnected.");
            }
            finally
            {
                sessionActive = false;
                status.Text = "DISCONNECTED";
                connect.Text = "CONNECT";
                connect.Enabled = true;
            }
            return;
        }

        var h = host.Text.Trim();
        var v = version.Text.Trim();
        var roomId = room.Text.Trim();
        var rawCookie = cookie.Text.Trim();

        if (string.IsNullOrWhiteSpace(h) || string.IsNullOrWhiteSpace(v) || string.IsNullOrWhiteSpace(rawCookie))
        {
            Append("Host, game version and mc_jwt cookie are required.");
            return;
        }

        if (string.IsNullOrWhiteSpace(roomId))
        {
            roomId = GenerateRoomId();
            room.Text = roomId;
        }

        documentId = Guid.NewGuid().ToString();
        var uri = BuildSocketUri(h, v, roomId, documentId, 1, "navigate");
        var normalizedCookie = rawCookie.Contains("mc_jwt", StringComparison.OrdinalIgnoreCase) ? rawCookie : "mc_jwt=" + rawCookie;

        status.Text = "CONNECTING";
        connect.Text = "DISCONNECT";
        connect.Enabled = false;
        sessionActive = true;

        try
        {
            await client.ConnectAsync(new SessionOptions(uri, normalizedCookie, DefaultUa, "https://" + h));
            runtime = new AutomationRuntime(client);
            runtime.Controller.Log += Append;
            automationCts = new CancellationTokenSource();
            _ = runtime.Controller.RunAsync(automationCts.Token);
            status.Text = "SYNCING — WAITING FOR WELCOME";
            Append("Socket opened; SocketOpened sent; waiting for authoritative Welcome.");
        }
        catch (Exception e)
        {
            Append("CONNECT FAILED " + e.Message);
            await client.DisconnectAsync();
            sessionActive = false;
            status.Text = "DISCONNECTED";
            connect.Text = "CONNECT";
        }
        finally { connect.Enabled = true; }
    }

    static Uri BuildSocketUri(string host, string version, string room, string documentId, int attempt, string navigationType)
    {
        // Exact Android UrlBuilder parameter values: JSON-encoded strings, then URL encoded.
        var query = new[]
        {
            Pair("surface", "\"web\""),
            Pair("platform", "\"desktop\""),
            Pair("version", "\"" + version + "\""),
            Pair("capabilities", "\"fbo_mipmap_unsupported\""),
            Pair("locale", "\"en\""),
            Pair("clientDocumentId", "\"" + documentId + "\""),
            Pair("clientConnectionAttempt", attempt.ToString()),
            Pair("clientNavigationType", "\"" + navigationType + "\""),
            Pair("clientVisibilityState", "\"visible\"")
        };
        return new Uri($"wss://{host}/version/{Uri.EscapeDataString(version)}/api/rooms/{Uri.EscapeDataString(room)}/connect?{string.Join("&", query)}");
    }

    static string Pair(string key, string value) => Uri.EscapeDataString(key) + "=" + Uri.EscapeDataString(value);

    static string GenerateRoomId()
    {
        const string chars = "abcdefghijklmnopqrstuvwxyz";
        Span<byte> bytes = stackalloc byte[10];
        System.Security.Cryptography.RandomNumberGenerator.Fill(bytes);
        var result = new char[10];
        for (var i = 0; i < result.Length; i++) result[i] = chars[bytes[i] % chars.Length];
        return new string(result);
    }

    void Append(string s)
    {
        if (InvokeRequired) { BeginInvoke(() => Append(s)); return; }
        log.AppendText($"[{DateTime.Now:T}] {s}{Environment.NewLine}");
    }

    void Ui(Action a) { if (InvokeRequired) BeginInvoke(a); else a(); }

    protected override async void OnFormClosed(FormClosedEventArgs e)
    {
        automationCts?.Cancel();
        await client.DisposeAsync();
        base.OnFormClosed(e);
    }
}
