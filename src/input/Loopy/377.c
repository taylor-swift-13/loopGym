// Source: data/benchmarks/sv-benchmarks/loop-lit/gsv2008.c
#define LARGE_INT 1000000
extern int unknown_int(void);

/*@
  requires -1000 < y && y < LARGE_INT;
*/
void loopy_377(int y) {
    int x;
    x = -50;
    
    while (x < 0) {
	x = x + y;
	y++;
    }
    {;
//@ assert(y > 0);
}

    return;
}