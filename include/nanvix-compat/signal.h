/* Compatibility signal.h wrapper for Nanvix.
 * Adds SA_RESTART which is not defined in Nanvix's signal.h. */
#ifndef _NANVIX_COMPAT_SIGNAL_H
#define _NANVIX_COMPAT_SIGNAL_H

#include_next <signal.h>

#ifdef __nanvix__
# ifndef SA_RESTART
#  define SA_RESTART 0x10000000
# endif
#endif

#endif /* _NANVIX_COMPAT_SIGNAL_H */
