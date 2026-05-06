/* Stub net/if.h for Nanvix.
 * BusyBox's libbb/xconnect.c includes this unconditionally. */
#ifndef _NET_IF_H
#define _NET_IF_H

#define IF_NAMESIZE 16
#define IFNAMSIZ IF_NAMESIZE

struct if_nameindex {
    unsigned int if_index;
    char *if_name;
};

#endif /* _NET_IF_H */
