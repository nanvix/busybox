/* Nanvix compatibility shim for <sys/stat.h>.
 * Defines UTIME_NOW and UTIME_OMIT before including the real header.
 */
#ifndef _NANVIX_COMPAT_SYS_STAT_H
#define _NANVIX_COMPAT_SYS_STAT_H

#ifndef UTIME_NOW
#define UTIME_NOW  ((1L << 30) - 1L)
#endif
#ifndef UTIME_OMIT
#define UTIME_OMIT ((1L << 30) - 2L)
#endif

#include_next <sys/stat.h>

#endif /* _NANVIX_COMPAT_SYS_STAT_H */
