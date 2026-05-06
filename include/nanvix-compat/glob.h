/* Compatibility glob.h wrapper for Nanvix.
 * Adds GLOB_NOMATCH which is not defined in Nanvix's glob.h. */
#ifndef _NANVIX_COMPAT_GLOB_H
#define _NANVIX_COMPAT_GLOB_H

#include_next <glob.h>

#ifdef __nanvix__
# ifndef GLOB_NOMATCH
#  define GLOB_NOMATCH (-3)
# endif
#endif

#endif /* _NANVIX_COMPAT_GLOB_H */
