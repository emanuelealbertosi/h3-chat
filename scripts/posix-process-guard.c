/* macOS: track forks with kqueue, including descendants that call setsid().
 * The executable is a private child supervisor, never a privileged service. */
#include <sys/event.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <signal.h>
#include <unistd.h>
#include <errno.h>
#include <stdlib.h>

static volatile sig_atomic_t stopped=0;
static void stop(int s){(void)s;stopped=1;}
int main(int argc,char **argv){
 if(argc<2)return 125;
 pid_t parent=getppid(),pids[4096];int count=0,gate[2];
 if(pipe(gate))return 125;
 int queue=kqueue();if(queue<0)return 125;
 pid_t child=fork();if(child<0)return 125;
 if(!child){close(gate[1]);char value;if(read(gate[0],&value,1)!=1)_exit(125);close(gate[0]);close(queue);execvp(argv[1],argv+1);_exit(127);}
 close(gate[0]);pids[count++]=child;
 struct kevent change,events[64];
 EV_SET(&change,child,EVFILT_PROC,EV_ADD|EV_ENABLE,NOTE_FORK|NOTE_TRACK|NOTE_EXIT,0,NULL);
 if(kevent(queue,&change,1,NULL,0,NULL)<0){kill(child,SIGKILL);return 125;}
 signal(SIGTERM,stop);signal(SIGINT,stop);signal(SIGHUP,stop);
 if(write(gate[1],"1",1)!=1){kill(child,SIGKILL);return 125;}close(gate[1]);
 int status=0,done=0,failed=0;
 while(!stopped&&!done&&getppid()==parent){
  struct timespec wait={0,100000000};int n=kevent(queue,NULL,0,events,64,&wait);
  if(n<0&&errno!=EINTR){failed=1;break;}
  for(int i=0;i<n;i++){
   pid_t pid=(pid_t)events[i].ident;
   if(events[i].fflags&NOTE_TRACKERR){failed=1;stopped=1;}
   if(events[i].fflags&NOTE_CHILD){if(count==4096){failed=1;stopped=1;}else pids[count++]=pid;}
   if(events[i].fflags&NOTE_EXIT){
    if(pid==child)done=1;
    else for(int j=0;j<count;j++)if(pids[j]==pid){pids[j]=0;break;}
   }
  }
 }
 /* Drain queued fork notifications before killing detached descendants. */
 struct timespec now={0,0};int n;
 while((n=kevent(queue,NULL,0,events,64,&now))>0)for(int i=0;i<n;i++)
  if((events[i].fflags&NOTE_CHILD)&&count<4096)pids[count++]=(pid_t)events[i].ident;
 for(int i=count-1;i>=0;i--)if(pids[i]>0)kill(pids[i],SIGKILL);
 while(waitpid(child,&status,0)<0&&errno==EINTR){}
 close(queue);
 if(failed)return 125;
 if(stopped)return 130;
 return WIFEXITED(status)?WEXITSTATUS(status):128+WTERMSIG(status);
}
