/* Stub sys/sysmacros.h for Nanvix.
 * Provides major/minor/makedev macros that BusyBox expects. */
#ifndef _SYS_SYSMACROS_H
#define _SYS_SYSMACROS_H

#ifndef major
#define major(dev) ((unsigned int)(((dev) >> 8) & 0xff))
#endif
#ifndef minor
#define minor(dev) ((unsigned int)((dev) & 0xff))
#endif
#ifndef makedev
#define makedev(maj, min) ((dev_t)(((maj) << 8) | (min)))
#endif

#endif /* _SYS_SYSMACROS_H */
