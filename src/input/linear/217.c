int unknown();
void foo217() {

    int invalid;
    int unowned;
    int nonexclusive;
    int exclusive;
    int RETURN;


        exclusive = unknown();
    invalid = unknown();
    nonexclusive = unknown();
    unowned = unknown();

    while(!((nonexclusive + unowned) >= 1 && invalid >= 1)) {
       if(invalid >= 1){
       if(unknown()){
       nonexclusive = nonexclusive + exclusive;
       exclusive = 0;
       invalid = invalid - 1;
       unowned = unowned + 1;
      }
       else{
       exclusive = 1;
       unowned = 0;
       nonexclusive = 0;
      }
      }
       else if((nonexclusive + unowned) >= 1){
       invalid = invalid + unowned + nonexclusive - 1;
       nonexclusive = 0;
       exclusive = exclusive + 1;
       unowned = 0;
      }
      }

  }