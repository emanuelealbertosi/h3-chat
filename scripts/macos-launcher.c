#include <mach-o/dyld.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    char executable[PATH_MAX], root[PATH_MAX], python[PATH_MAX], launcher[PATH_MAX];
    uint32_t size=sizeof(executable);
    if (_NSGetExecutablePath(executable,&size) || !realpath(executable,root)) return 1;
    for(int i=0;i<4;i++){char *slash=strrchr(root,'/');if(!slash)return 1;*slash=0;}
    if(chdir(root))return 1;
    snprintf(python,sizeof(python),"%s/runtime/python/bin/python3",root);
    snprintf(launcher,sizeof(launcher),"%s/launcher.py",root);
    char **args=calloc((size_t)argc+4,sizeof(char *));
    if(!args)return 1;
    args[0]=python;args[1]="-X";args[2]="utf8";args[3]=launcher;
    int next=4;
    for(int i=1;i<argc;i++)if(strncmp(argv[i],"-psn_",5)!=0)args[next++]=argv[i];
    execv(python,args);
    perror("H3-Chat: impossibile avviare Python. Mantieni insieme tutti i file della cartella estratta");
    return 1;
}
