// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/ex14n.v.c
extern int unknown_int(void);

void loopy_86(int y, int N, int v1, int v2, int v3) {

    	int x;
   	
   	x=1;
   	while (x <= N){
      		y=N-x;

		if(y < 0 || y >= N)
			{;
//@ assert(0 == 1);
}

      		x++;
		v1 = v2;
		v2 = v3;
		v3 = v1;
	
   	}

   	return;

}