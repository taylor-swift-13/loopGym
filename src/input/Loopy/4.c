// Source: data/benchmarks/LinearArbitrary-SeaHorn/VeriMAP/MAP-interpolants_needed-pepm-proc.c_VeriMAP_true.c
extern int unknown_int(void);

void loopy_4(void){

	int x=0;
	int y=0;

	while (unknown_int()) {
		if (unknown_int()) {
			x = x+1; 
			y = y+2;
		} else if (unknown_int()) {
			if (x >= 4) {
			    x = x+1; 
			    y = y+3; 
			}
		} 
	}

    if(3*x < y)
		goto ERROR;
	
	return;
{ ERROR: {; 
//@ assert(\false);
}
}
	return;
}