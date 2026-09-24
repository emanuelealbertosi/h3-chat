using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

class Launcher {
  [STAThread]
  static void Main(string[] args) {
    string root=AppDomain.CurrentDomain.BaseDirectory;
    bool stop=Array.IndexOf(args,"--stop")>=0;
    string python=Path.Combine(root,"runtime","python",stop?"pythonw.exe":"python.exe");
    if(!File.Exists(python)) {MessageBox.Show("Prima esegui Installa-H3-Chat.bat per preparare il runtime locale.","H3-Chat");return;}
    try {
      ProcessStartInfo info=new ProcessStartInfo(python,"-X utf8 -u \""+Path.Combine(root,"launcher.py")+"\""+(stop?" --stop":Array.IndexOf(args,"--logs-only")>=0?" --logs-only":""));
      info.WorkingDirectory=root;info.UseShellExecute=false;info.CreateNoWindow=stop;
      Process.Start(info);
    } catch(Exception e){MessageBox.Show(e.Message,"H3-Chat");}
  }
}
