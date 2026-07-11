// Source: data/benchmarks/LinearArbitrary-SeaHorn/VeriMAP/MAP-singleloop2-pepm-proc.c_VeriMAP_true.c
extern int unknown_int(void);

;
/*@
  requires n>=1;
*/
void loopy_5(int n) {
int x=0;
int y=0;


	

	while(x < 2*n){
	   x = x + 1;

	   if ( x > n )
		  y = y - 1;
	   else
		  y = y + 2;
	}

	if(x < y)
		goto ERROR;

	return;
{ ERROR: {; 
//@ assert(\false);
}
}
	return;
}