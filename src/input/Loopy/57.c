// Source: data/benchmarks/LinearArbitrary-SeaHorn/loops/loop-lit/gj2007b_true-unreach-call_true-termination.c
extern int unknown_int(void);

void loopy_57(int n) {
    int x = 0;
    int m = 0;
    
    while(x < n) {
	if(unknown_int()) {
	    m = x;
	}
	x = x + 1;
    }
    {;
//@ assert((m >= 0 || n <= 0));
}

    {;
//@ assert((m < n || n <= 0));
}

    return;
}