// Source: data/benchmarks/LinearArbitrary-SeaHorn/loops/loop-lit/gsv2008_true-unreach-call_true-termination.c
#define LARGE_INT 1000000
extern int unknown_int(void);

/*@
  requires -1000 < y && y < LARGE_INT;
*/
void loopy_59(int y) {
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