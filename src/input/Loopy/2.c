// Source: data/benchmarks/LinearArbitrary-SeaHorn/VeriMAP/MAP-disj_VeriMAP_true.c

void loopy_2(void) {
   int x, y;

   x = 0;
   y = 50;

  while( x < 100 ) {
    if( x < 50 ) {
      x = x+1;
    } else {
      x = x+1;
      y = y+1;
    }
  }

  if( y > 100 || y < 100 )
    goto ERROR;

return;

{ ERROR: {; 
//@ assert(\false);
}
}

}