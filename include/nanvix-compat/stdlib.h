/* Compatibility wrapper for stdlib.h on Nanvix.
 * Hides newlib's utoa/itoa declarations which conflict with BusyBox's
 * own definitions (different function signatures). */
#ifndef _NANVIX_COMPAT_STDLIB_H
#define _NANVIX_COMPAT_STDLIB_H

/* Temporarily rename newlib's utoa/itoa to avoid declaration conflicts */
#ifdef __nanvix__
# define utoa __newlib_utoa_hidden
# define itoa __newlib_itoa_hidden
#endif

#include_next <stdlib.h>

#ifdef __nanvix__
# undef utoa
# undef itoa
#endif

#endif /* _NANVIX_COMPAT_STDLIB_H */
