// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/afnp2014_true-unreach-call.c
extern int unknown_int(void);

void loopy_80(void) {
    int x = 1;
    int y = 0;
    while (y < 1000 && unknown_int()) {
	x = x + y;
	y = y + 1;
    }
    {;
//@ assert(x >= y);
}

}