using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

class Launcher {
  [STAThread]
  static void Main(string[] args) {
    string root=AppDomain.CurrentDomain.BaseDirectory;
    string python=Path.Combine(root,"runtime","python","pythonw.exe");
    if(!File.Exists(python)) {MessageBox.Show("Prima esegui Installa-H3-Chat.bat per preparare il runtime locale.","H3-Chat");return;}
    try {
      ProcessStartInfo info=new ProcessStartInfo(python,"\""+Path.Combine(root,"launcher.py")+"\""+(Array.IndexOf(args,"--stop")>=0?" --stop":""));
      info.WorkingDirectory=root;info.UseShellExecute=false;info.CreateNoWindow=true;
      Process.Start(info);
    } catch(Exception e){MessageBox.Show(e.Message,"H3-Chat");}
  }
}
