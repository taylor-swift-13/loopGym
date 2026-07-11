// Source: data/benchmarks/LinearArbitrary-SeaHorn/loops/loop-lit/css2003_true-unreach-call_true-termination.c
#define LARGE_INT 1000000
extern int unknown_int(void);

/*@
  requires 0 <= k && k <= 1;
*/
void loopy_54(int k) {
    int i, j;
    i = 1;
    j = 1;
    
    while (i < LARGE_INT) {
	i = i + 1;
	j = j + k;
	k = k - 1;
	{;
//@ assert(1 <= i + k && i + k <= 2 && i >= 1);
}

    }
    return;
}