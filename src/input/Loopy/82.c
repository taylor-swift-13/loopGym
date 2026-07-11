// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/cegar2.v.c
extern int unknown_int(void);

void loopy_82(int N, int input, int v1, int v2, int v3) {

	
	int x = 0;
	int m = 0;
	

 	while (x < N) {

		input = unknown_int();
		if( input ) {

			m = x;
		}

		x = x + 1;
		v1 = unknown_int();
		v2 = unknown_int();
		v3 = unknown_int();

	}

	if (N > 0) {
		{;
//@ assert((0 <= m) && (m < N));
}

	}

}