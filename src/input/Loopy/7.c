// Source: data/benchmarks/LinearArbitrary-SeaHorn/VeriMAP/TRACER-testabs12_VeriMAP_true.c
extern unsigned int unknown_uint(void);

;

void errorFn() {ERROR: goto ERROR;}
/*@
  requires count >= 0;
*/
void loopy_7(int count, int n){
  int i;
  
  i=0;

  while (i < 100 ){
      count++;
      i++;
  }

  {;
//@ assert(!( (i > 100 ) || count < 0 ));
}

}