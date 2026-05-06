/* Stub sys/socket.h additions for Nanvix.
 * Provides SOCK_RDM which is not defined in Nanvix's socket.h. */
#ifndef _NANVIX_COMPAT_SOCKET_H
#define _NANVIX_COMPAT_SOCKET_H

/* Include the real sys/socket.h first */
#include_next <sys/socket.h>

/* Define SOCK_RDM if not already defined */
#ifndef SOCK_RDM
#define SOCK_RDM 4
#endif

#endif /* _NANVIX_COMPAT_SOCKET_H */
