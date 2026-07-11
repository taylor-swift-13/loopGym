// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/w1.c
extern int unknown_int(void);

/*@
  requires !(n < 0);
*/
void loopy_115(int n) {
	
	

	int x = 0;

 	while (x < n) {

		x = x + 1;

	}
	{;
//@ assert(x == n);
}

}