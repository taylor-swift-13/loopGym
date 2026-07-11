// Source: data/benchmarks/LinearArbitrary-SeaHorn/VeriMAP/TRACER-testabs7_VeriMAP_true.c

void errorFn() {ERROR: goto ERROR;}
void loopy_10(int n){
  int i;

  i=0;n=10;
  while (i < n){ i++; }

  {;
//@ assert(!( i>10 ));
}

}