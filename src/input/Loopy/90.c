// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/fig3.v.c
extern int unknown_int(void);

void loopy_90(int y, int v1, int v2, int v3, int x, int input) {

	
	int lock;
	lock = 0;
	
	

	{
		lock = 1;
		x = y;
		if( input ) {

			lock = 0;
			y = y + 1;
		}

	}

	while(x != y) {

		lock = 1;
		x = y;
		input = unknown_int();
		if ( input ) {

			lock = 0;
			y = y + 1;
		}
		v1 = unknown_int();
		v2 = unknown_int();
		v3 = unknown_int();
	}

	{;
//@ assert(lock == 1);
}

}
