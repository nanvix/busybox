/*
 * nanvix_stubs.c - Stub implementations for POSIX functions not available
 * in the Nanvix kernel/libc. These allow BusyBox to link and run with
 * limited functionality.
 */

#include <sys/types.h>
#include <sys/signal.h>
#include <errno.h>
#include <stddef.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

/* Runtime init/fini (called by Nanvix kernel at process start/exit) */
void _init(void) {}
void _fini(void) {}

/* glibc-specific: mallopt is a no-op on newlib */
int mallopt(int param, int value)
{
    (void)param; (void)value;
    return 1; /* success */
}

/* Signal handling stubs */
int sigaction(int signum, const struct sigaction *act, struct sigaction *oldact)
{
    (void)signum; (void)act; (void)oldact;
    return 0;
}

int sigprocmask(int how, const sigset_t *set, sigset_t *oldset)
{
    (void)how; (void)set; (void)oldset;
    return 0;
}

int sigsuspend(const sigset_t *mask)
{
    (void)mask;
    errno = EINTR;
    return -1;
}

/* Process management stubs */
pid_t getppid(void)
{
    return 1; /* return init as parent */
}

pid_t setsid(void)
{
    return getpid();
}

pid_t vfork(void)
{
    return fork();
}

int getgroups(int size, gid_t *list)
{
    (void)size; (void)list;
    return 0; /* no supplementary groups */
}

/* User/password database stub */
#include <pwd.h>

static struct passwd _stub_pw = {
    .pw_name = "root",
    .pw_passwd = "",
    .pw_uid = 0,
    .pw_gid = 0,
    .pw_dir = "/",
    .pw_shell = "/bin/sh"
};

struct passwd *getpwnam(const char *name)
{
    (void)name;
    return &_stub_pw;
}

/* Environment */
int clearenv(void)
{
    extern char **environ;
    if (environ)
        environ[0] = NULL;
    return 0;
}

/* Clock/time stubs */
int clock_settime(clockid_t clk_id, const struct timespec *tp)
{
    (void)clk_id; (void)tp;
    errno = EPERM;
    return -1;
}

int settimeofday(const void *tv, const void *tz)
{
    (void)tv; (void)tz;
    errno = EPERM;
    return -1;
}

/* Filesystem stubs */
int mknod(const char *pathname, mode_t mode, dev_t dev)
{
    (void)pathname; (void)mode; (void)dev;
    errno = ENOSYS;
    return -1;
}

/* TTY stub */
int ttyname_r(int fd, char *buf, size_t buflen)
{
    (void)fd;
    if (buflen < 9)
        return ERANGE;
    strcpy(buf, "/dev/tty");
    return 0;
}

/* dirname - should be in libc but isn't in this newlib build */
char *dirname(char *path)
{
    static char dot[] = ".";
    char *last_slash;

    if (path == NULL || *path == '\0')
        return dot;

    last_slash = strrchr(path, '/');
    if (last_slash == NULL)
        return dot;

    if (last_slash == path)
        return path[1] ? (char *)"/" : dot;

    *last_slash = '\0';
    return path;
}

/* Pattern matching stubs - fnmatch, glob, regex */
#define FNM_NOMATCH 1
int fnmatch(const char *pattern, const char *string, int flags)
{
    (void)flags;
    /* Very simple matching: just do strcmp for exact match */
    if (strcmp(pattern, string) == 0)
        return 0;
    /* Handle '*' wildcard at the simplest level */
    if (pattern[0] == '*' && pattern[1] == '\0')
        return 0;
    return FNM_NOMATCH;
}

/* Minimal glob stub */
typedef struct {
    size_t gl_pathc;
    char **gl_pathv;
    size_t gl_offs;
} glob_t;

int glob(const char *pattern, int flags,
         int (*errfunc)(const char *, int), glob_t *pglob)
{
    (void)pattern; (void)flags; (void)errfunc;
    if (pglob) {
        pglob->gl_pathc = 0;
        pglob->gl_pathv = NULL;
    }
    return 3; /* GLOB_NOMATCH */
}

void globfree(glob_t *pglob)
{
    (void)pglob;
}

/* Regex stubs */
typedef struct { int re_nsub; } regex_t;
typedef int regoff_t;
typedef struct { regoff_t rm_so; regoff_t rm_eo; } regmatch_t;

int regcomp(regex_t *preg, const char *regex, int cflags)
{
    (void)preg; (void)regex; (void)cflags;
    if (preg) preg->re_nsub = 0;
    return 0;
}

int regexec(const regex_t *preg, const char *string, size_t nmatch,
            regmatch_t pmatch[], int eflags)
{
    (void)preg; (void)string; (void)nmatch; (void)pmatch; (void)eflags;
    return 1; /* REG_NOMATCH */
}

size_t regerror(int errcode, const regex_t *preg, char *errbuf, size_t errbuf_size)
{
    (void)errcode; (void)preg;
    if (errbuf && errbuf_size > 0) {
        strncpy(errbuf, "regex not supported", errbuf_size - 1);
        errbuf[errbuf_size - 1] = '\0';
    }
    return 20;
}

void regfree(regex_t *preg)
{
    (void)preg;
}

/* WCOREDUMP macro - used as a function reference by BusyBox */
int WCOREDUMP(int status)
{
    (void)status;
    return 0;
}
