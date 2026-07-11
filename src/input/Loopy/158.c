// Source: data/benchmarks/accelerating_invariant_generation/cav/pldi082_unbounded.c

/*@
  requires !(N < 0);
*/
void loopy_158(int N){

  int x = 0;
  int y = 0;
  

  

  while (1){
     if (x <= N)
        y++;
     else if(x >= N+1)
       y--;
     else return;

     if ( y < 0)
       break;
     x++;
  }

  if(N >= 0)
    if(y == -1)
      if (x >= 2 * N + 3)
        goto ERROR;

  return;
{ ERROR: {; 
//@ assert(\false);
}
}
}
