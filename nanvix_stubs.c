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

struct passwd *getpwuid(uid_t uid)
{
    (void)uid;
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

/* Group database stubs */
#include <grp.h>

static char *_stub_gr_mem[] = { NULL };

static struct group _stub_gr = {
    .gr_name = "root",
    .gr_passwd = "",
    .gr_gid = 0,
    .gr_mem = _stub_gr_mem
};

struct group *getgrnam(const char *name)
{
    (void)name;
    return &_stub_gr;
}

struct group *getgrgid(gid_t gid)
{
    (void)gid;
    return &_stub_gr;
}

struct group *getgrent(void) { return NULL; }
void setgrent(void) {}
void endgrent(void) {}

void setpwent(void) {}
void endpwent(void) {}
struct passwd *getpwent(void) { return NULL; }

/* ------------------------------------------------------------------ */
/* POSIX fnmatch() — handles *, ?, [...], FNM_PATHNAME, FNM_PERIOD   */
/* ------------------------------------------------------------------ */
#include <fnmatch.h>

static int _fnmatch_internal(const char *p, const char *s,
                             const char *s_start, int flags)
{
    int negate, matched;
    char c, sc;

    while ((c = *p++) != '\0') {
        sc = *s;

        switch (c) {
        case '?':
            if (sc == '\0')
                return FNM_NOMATCH;
            if ((flags & FNM_PATHNAME) && sc == '/')
                return FNM_NOMATCH;
            if ((flags & FNM_PERIOD) && sc == '.' &&
                (s == s_start ||
                 ((flags & FNM_PATHNAME) && *(s-1) == '/')))
                return FNM_NOMATCH;
            s++;
            break;

        case '*':
            /* Collapse consecutive stars */
            while (*p == '*')
                p++;

            if ((flags & FNM_PERIOD) && sc == '.' &&
                (s == s_start ||
                 ((flags & FNM_PATHNAME) && *(s-1) == '/')))
                return FNM_NOMATCH;

            /* Trailing star matches everything (respecting FNM_PATHNAME) */
            if (*p == '\0') {
                if (flags & FNM_PATHNAME)
                    return (strchr(s, '/') ? FNM_NOMATCH : 0);
                return 0;
            }

            /* Try matching rest of pattern at every position */
            for (; *s != '\0'; s++) {
                if ((flags & FNM_PATHNAME) && *s == '/')
                    break;
                if (_fnmatch_internal(p, s, s_start,
                                     flags & ~FNM_PERIOD) == 0)
                    return 0;
            }
            return _fnmatch_internal(p, s, s_start, flags & ~FNM_PERIOD);

        case '[':
            if (sc == '\0')
                return FNM_NOMATCH;
            if ((flags & FNM_PATHNAME) && sc == '/')
                return FNM_NOMATCH;

            negate = 0;
            if (*p == '!' || *p == '^') {
                negate = 1;
                p++;
            }

            matched = 0;
            while ((c = *p++) != '\0' && c != ']') {
                /* Range: a-z */
                if (*p == '-' && *(p + 1) != '\0' && *(p + 1) != ']') {
                    char c2 = *(p + 1);
                    p += 2;
                    if ((unsigned char)sc >= (unsigned char)c &&
                        (unsigned char)sc <= (unsigned char)c2)
                        matched = 1;
                } else {
                    if (sc == c)
                        matched = 1;
                }
            }

            if (c == '\0')
                return FNM_NOMATCH; /* unterminated bracket */

            if (negate ? matched : !matched)
                return FNM_NOMATCH;
            s++;
            break;

        case '\\':
            if (!(flags & FNM_NOESCAPE)) {
                c = *p++;
                if (c == '\0')
                    return FNM_NOMATCH;
            }
            /* fall through to literal match */
            /* FALLTHROUGH */
        default:
            if (c != sc)
                return FNM_NOMATCH;
            s++;
            break;
        }
    }

    return (*s == '\0') ? 0 : FNM_NOMATCH;
}

int fnmatch(const char *pattern, const char *string, int flags)
{
    return _fnmatch_internal(pattern, string, string, flags);
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

/* Host ID stub */
long gethostid(void)
{
    return 0x007f0101; /* 127.1.1 */
}

/* Group list stub - used by id applet */
int getgrouplist(const char *user, gid_t group,
                 gid_t *groups, int *ngroups)
{
    (void)user;
    if (*ngroups >= 1) {
        groups[0] = group;
        *ngroups = 1;
        return 1;
    }
    *ngroups = 1;
    return -1;
}

/* Login name stub */
int getlogin_r(char *buf, size_t bufsize)
{
    if (bufsize < 5)
        return ERANGE;
    strcpy(buf, "root");
    return 0;
}

/* Terminal speed stubs - used by stty */
#include <termios.h>

speed_t cfgetispeed(const struct termios *tp)
{
    return tp ? (tp->c_cflag & 0xf) : B9600;
}

speed_t cfgetospeed(const struct termios *tp)
{
    return tp ? (tp->c_cflag & 0xf) : B9600;
}

int cfsetispeed(struct termios *tp, speed_t speed)
{
    if (tp) tp->c_cflag = (tp->c_cflag & ~0xf) | (speed & 0xf);
    return 0;
}

int cfsetospeed(struct termios *tp, speed_t speed)
{
    if (tp) tp->c_cflag = (tp->c_cflag & ~0xf) | (speed & 0xf);
    return 0;
}

/* sync - flush filesystem buffers */
void sync(void)
{
    /* No global sync on Nanvix; individual fsync is available */
}

/* wait - wrapper around waitpid */
pid_t wait(int *wstatus)
{
    return waitpid(-1, wstatus, 0);
}

/* CPU affinity stub - used by nproc via libbb */
int sched_getaffinity(pid_t pid, size_t cpusetsize, void *mask)
{
    (void)pid;
    /* Set bit 0 to indicate one CPU */
    if (mask && cpusetsize > 0) {
        memset(mask, 0, cpusetsize);
        ((unsigned char *)mask)[0] = 1;
    }
    return 0;
}
