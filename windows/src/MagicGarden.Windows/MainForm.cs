using System.Text.Json;
using MagicGarden.Windows.Core.Automation;
using MagicGarden.Windows.Core.Protocol;

namespace MagicGarden.Windows;

public sealed class MainForm:Form
{
 readonly TextBox room=new(){PlaceholderText="WebSocket URL",Dock=DockStyle.Top};
 readonly TextBox cookie=new(){PlaceholderText="mc_jwt cookie",Dock=DockStyle.Top,UseSystemPasswordChar=true};
 readonly Button connect=new(){Text="CONNECT",Dock=DockStyle.Top,Height=38};
 readonly Label status=new(){Text="DISCONNECTED",Dock=DockStyle.Top,Height=28};
 readonly TabControl tabs=new(){Dock=DockStyle.Fill};
 readonly TextBox log=new(){Dock=DockStyle.Bottom,Multiline=true,ReadOnly=true,Height=150,ScrollBars=ScrollBars.Vertical};
 readonly RoomClient client=new(); CancellationTokenSource? automationCts; AutomationRuntime? runtime;
 public MainForm()
 {
  Text="Magic Garden";Width=1000;Height=720;StartPosition=FormStartPosition.CenterScreen;
  Controls.Add(tabs);Controls.Add(log);Controls.Add(status);Controls.Add(connect);Controls.Add(cookie);Controls.Add(room);
  foreach(var x in new[]{"A — Auto Plant","B — Harvest / Sell","C — Auto Shop","D — Emergency Feed","E — Eggs","F — Pet Teams"})tabs.TabPages.Add(MakePage(x));
  connect.Click+=async(_,__)=>await Toggle();
  client.ProtocolWarning+=x=>Ui(()=>Append("WARN "+x)); client.MessageApplied+=_=>Ui(()=>status.Text=client.IsAuthoritativeReady?"CONNECTED — AUTHORITATIVE STATE":"SYNCING");
 }
 TabPage MakePage(string title){var p=new TabPage(title);p.Controls.Add(new Label{Text=title+" configuration",Dock=DockStyle.Top,Height=35});return p;}
 async Task Toggle()
 {
  if(client.IsAuthoritativeReady){automationCts?.Cancel();await client.DisconnectAsync();status.Text="DISCONNECTED";connect.Text="CONNECT";return;}
  if(!Uri.TryCreate(room.Text.Trim(),UriKind.Absolute,out var uri)){Append("Invalid WebSocket URL.");return;}
  status.Text="CONNECTING";connect.Enabled=false;
  try{
   await client.ConnectAsync(new SessionOptions(uri,cookie.Text.Trim(),"MagicGarden-Windows/1.0",uri.Scheme=="wss"?"https://"+uri.Host:"http://"+uri.Host));
   runtime=new AutomationRuntime(client);runtime.Controller.Log+=Append;automationCts=new();_=runtime.Controller.RunAsync(automationCts.Token);
   connect.Text="DISCONNECT";Append("Socket opened; waiting for authoritative Welcome.");
  }catch(Exception e){Append("CONNECT FAILED "+e.Message);status.Text="DISCONNECTED";}
  finally{connect.Enabled=true;}
 }
 void Append(string s){if(InvokeRequired){BeginInvoke(()=>Append(s));return;}log.AppendText($"[{DateTime.Now:T}] {s}{Environment.NewLine}");}
 void Ui(Action a){if(InvokeRequired)BeginInvoke(a);else a();}
 protected override async void OnFormClosed(FormClosedEventArgs e){automationCts?.Cancel();await client.DisposeAsync();base.OnFormClosed(e);}
}