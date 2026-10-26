/* macOS: kqueue fork notifications plus libproc descendant inventory.
 * The executable is a private child supervisor, never a privileged service. */
#include <sys/event.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/resource.h>
#include <signal.h>
#include <unistd.h>
#include <errno.h>
#include <stdlib.h>
#include <libproc.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>

/* XNU proc_info flavor 17. Original parent identity survives reparenting,
 * unlike proc_listchildpids. Keep the ABI local: the public SDK hides it.
 * apple-oss-distributions/xnu/bsd/sys/{proc_info_private,proc_internal}.h */
struct h3_unique {uint8_t uuid[16];uint64_t id,parent;int32_t version;uint32_t r2;uint64_t r3,r4;};
static uint64_t unique_ids[4096];
static int identity(pid_t pid,struct h3_unique *out){return proc_pidinfo(pid,17,0,out,sizeof(*out))==(int)sizeof(*out);}

static volatile sig_atomic_t stopped=0;
static void stop(int s){(void)s;stopped=1;}
static void discover(int queue,pid_t *pids,int *count){
 /* Inventory by original parent identity also finds a setsid child whose
  * ordinary parent exited between NOTE_FORK delivery and this inventory. */
 pid_t all[16384];int total=proc_listallpids(all,sizeof(all));
 for(int pass=0;pass<8;pass++){
  int added=0;
  for(int i=0;i<total;i++){
   struct h3_unique info;if(all[i]<=0||!identity(all[i],&info))continue;
   int known=0,parent=0;
   for(int k=0;k<*count;k++){known|=unique_ids[k]==info.id;parent|=unique_ids[k]==info.parent;}
   if(known||!parent)continue;
   if(*count==4096){stopped=1;return;}
   struct kevent event;EV_SET(&event,all[i],EVFILT_PROC,EV_ADD|EV_ENABLE,NOTE_FORK|NOTE_EXIT,0,NULL);
   if(kevent(queue,&event,1,NULL,0,NULL)==0){pids[*count]=all[i];unique_ids[(*count)++]=info.id;added=1;}
  }
  if(!added)break;
 }
 for(int i=0;i<*count;i++){
  if(pids[i]<=0)continue;
  pid_t children[4096];int bytes=proc_listchildpids(pids[i],children,sizeof(children));
  for(int j=0;j<bytes/(int)sizeof(pid_t);j++){
   pid_t pid=children[j];int found=0;for(int k=0;k<*count;k++)if(pids[k]==pid){found=1;break;}
   if(found||pid<=0)continue;
   if(*count==4096){stopped=1;return;}
   struct kevent event;EV_SET(&event,pid,EVFILT_PROC,EV_ADD|EV_ENABLE,NOTE_FORK|NOTE_EXIT,0,NULL);
   struct h3_unique info;
   if(identity(pid,&info)&&kevent(queue,&event,1,NULL,0,NULL)==0){pids[*count]=pid;unique_ids[(*count)++]=info.id;}
  }
 }
}
int main(int argc,char **argv){
 if(argc<2)return 125;
 pid_t parent=getppid(),pids[4096];int count=0,gate[2];
 if(pipe(gate))return 125;
 int queue=kqueue();if(queue<0)return 125;
 pid_t child=fork();if(child<0)return 125;
 if(!child){close(gate[1]);char value;if(read(gate[0],&value,1)!=1)_exit(125);close(gate[0]);close(queue);struct rlimit core={0,0},files={256,256};setrlimit(RLIMIT_CORE,&core);setrlimit(RLIMIT_NOFILE,&files);execvp(argv[1],argv+1);_exit(127);}
 close(gate[0]);struct h3_unique info;
 if(!identity(child,&info)){kill(child,SIGKILL);return 125;}
 pids[count]=child;unique_ids[count++]=info.id;
 struct kevent change,events[64];
 EV_SET(&change,child,EVFILT_PROC,EV_ADD|EV_ENABLE,NOTE_FORK|NOTE_EXIT,0,NULL);
 if(kevent(queue,&change,1,NULL,0,NULL)<0){perror("H3 process supervisor kqueue");kill(child,SIGKILL);return 125;}
 signal(SIGTERM,stop);signal(SIGINT,stop);signal(SIGHUP,stop);
 if(write(gate[1],"1",1)!=1){kill(child,SIGKILL);return 125;}close(gate[1]);
 int status=0,done=0,failed=0;
 while(!stopped&&!done&&getppid()==parent){
  struct timespec wait={0,20000000};int n=kevent(queue,NULL,0,events,64,&wait);
  if(n<0&&errno!=EINTR){failed=1;break;}
  discover(queue,pids,&count);
  for(int i=0;i<n;i++){
   pid_t pid=(pid_t)events[i].ident;
   if(events[i].fflags&NOTE_EXIT){
    if(pid==child)done=1;
    else for(int j=0;j<count;j++)if(pids[j]==pid){pids[j]=0;break;}
   }
  }
 }
 discover(queue,pids,&count);
 for(int i=count-1;i>=0;i--)if(pids[i]>0&&identity(pids[i],&info)&&info.id==unique_ids[i])kill(pids[i],SIGKILL);
 while(waitpid(child,&status,0)<0&&errno==EINTR){}
 close(queue);
 if(failed)return 125;
 if(stopped)return 130;
 return WIFEXITED(status)?WEXITSTATUS(status):128+WTERMSIG(status);
}
