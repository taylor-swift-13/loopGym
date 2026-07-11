// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/hola/10.c

extern int unknown2();

void loopy_123(void) {

	int w = 1;
	int z = 0;
	int x= 0;
	int y=0;

         while(unknown2()){
	    if(w) {
		x++; 
		w=!w;
	    };
	    if(!z) {
		y++; 
		z=!z;
	    };
	}

	{;
//@ assert(x==y);
}

}