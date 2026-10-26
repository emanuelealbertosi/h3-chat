/* Application-private child supervisor; preserves the ordinary user's GPU,
 * filesystem and network permissions. Sandbox confinement is a separate layer. */
#define _GNU_SOURCE
#include <sys/prctl.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <time.h>
static volatile sig_atomic_t stopped=0;
static void stop(int n){(void)n;stopped=1;}
static void cleanup(void){
 char path[128];snprintf(path,sizeof(path),"/proc/self/task/%d/children",getpid());
 for(int round=0;round<200;round++){
  FILE *f=fopen(path,"r");int count=0;pid_t pid;
  if(f){while(fscanf(f,"%d",&pid)==1){if(pid>0){kill(pid,SIGKILL);count++;}}fclose(f);}
  while(waitpid(-1,NULL,WNOHANG)>0){}
  if(!count)break;
  struct timespec tick={0,10000000};nanosleep(&tick,NULL);
 }
}
int main(int argc,char **argv){
 if(argc<2||prctl(PR_SET_CHILD_SUBREAPER,1,0,0,0))return 125;
 pid_t parent=getppid();signal(SIGTERM,stop);signal(SIGINT,stop);signal(SIGHUP,stop);
 pid_t child=fork();if(child<0)return 125;
 if(!child){pid_t owner=getppid();prctl(PR_SET_PDEATHSIG,SIGKILL,0,0,0);if(getppid()!=owner)_exit(125);setpgid(0,0);execvp(argv[1],argv+1);_exit(127);}
 int status=0,done=0;
 while(!stopped&&getppid()==parent){
  pid_t result=waitpid(child,&status,WNOHANG);if(result==child){done=1;break;}if(result<0&&errno!=EINTR)break;
  struct timespec tick={0,20000000};nanosleep(&tick,NULL);
 }
 cleanup();
 if(!done)return 130;
 return WIFEXITED(status)?WEXITSTATUS(status):128+WTERMSIG(status);
}
