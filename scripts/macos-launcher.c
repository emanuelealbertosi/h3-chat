#include <mach-o/dyld.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(void) {
    char executable[PATH_MAX], root[PATH_MAX], python[PATH_MAX], launcher[PATH_MAX];
    uint32_t size=sizeof(executable);
    if (_NSGetExecutablePath(executable,&size) || !realpath(executable,root)) return 1;
    for(int i=0;i<4;i++){char *slash=strrchr(root,'/');if(!slash)return 1;*slash=0;}
    if(chdir(root))return 1;
    snprintf(python,sizeof(python),"%s/runtime/python/bin/python3",root);
    snprintf(launcher,sizeof(launcher),"%s/launcher.py",root);
    char *args[]={python,"-X","utf8",launcher,NULL};
    execv(python,args);
    perror("H3-Chat: impossibile avviare Python. Mantieni insieme tutti i file della cartella estratta");
    return 1;
}
