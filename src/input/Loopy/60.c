// Source: data/benchmarks/LinearArbitrary-SeaHorn/loops/loop-lit/hhk2008_true-unreach-call_true-termination.c
extern int unknown_int(void);

/*@
  requires 0 <= b;
*/
void loopy_60(int a, int b) {
    
    
    int res, cnt;
    
    res = a;
    cnt = b;
    while (cnt > 0) {
	cnt = cnt - 1;
	res = res + 1;
    }
    {;
//@ assert(res == a + b);
}

    return;
}